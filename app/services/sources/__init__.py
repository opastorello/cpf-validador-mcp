"""Registro das fontes de consulta e despacho para a fonte ativa.

A fonte ativa é escolhida por `SOURCE` no .env (padrão `trt3`). Routers e MCP
falam só com `consultar()` e `consultar_multiplos()` daqui — nenhum deles sabe
qual serviço está do outro lado.

Cada fonte é dona do *como*: cliente HTTP, autenticação, CAPTCHA (ou nenhum),
parsing da resposta e limite de conexões simultâneas são problema dela. O que
esta camada padroniza é só o formato do resultado, descrito em `base.Fonte`.

Por isso o registro é preguiçoso: `trt3` carrega PyTorch para resolver CAPTCHA,
e não faz sentido pagar esse import quando a fonte ativa é outra que não usa
CAPTCHA nenhum. A classe só é importada quando a fonte é de fato usada.

Para adicionar uma fonte: escreva a classe (copie `exemplo.py`) e acrescente
uma linha em `_REGISTRO`.
"""
import importlib
import logging
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout, as_completed

from app import config as _cfg
from app import metrics as _m
from app.services.cpf import formatar
from app.services.sources.base import Fonte, mascarar_cpf

log = logging.getLogger("consulta")

#: nome -> (módulo, classe, rótulo legível)
_REGISTRO: dict[str, tuple[str, str, str]] = {
    "trt3": (
        "app.services.sources.trt3",
        "TRT3",
        "TRT 3ª Região (certidao.trt3.jus.br)",
    ),
    "tcu": (
        "app.services.sources.tcu",
        "TCU",
        "TCU — Contas Julgadas Irregulares (certidoes.apps.tcu.gov.br)",
    ),
    "exemplo": (
        "app.services.sources.exemplo",
        "Exemplo",
        "Fonte de exemplo (dados fictícios, não consulta nada)",
    ),
}

_instancias: dict[str, Fonte] = {}


def fontes_disponiveis() -> dict[str, str]:
    """Mapa nome -> rótulo de todas as fontes registradas, sem importá-las."""
    return {nome: rotulo for nome, (_, _, rotulo) in _REGISTRO.items()}


def get_fonte(nome: str | None = None) -> Fonte:
    """Devolve a fonte pedida, ou a ativa (`SOURCE`) quando `nome` é None.

    A classe é importada na primeira vez que a fonte é usada e reaproveitada
    depois.
    """
    escolhida = (nome or _cfg.SOURCE).strip().lower()
    if escolhida not in _REGISTRO:
        raise ValueError(
            f"Fonte desconhecida: {escolhida!r}. Disponíveis: {', '.join(sorted(_REGISTRO))}"
        )
    if escolhida not in _instancias:
        modulo, classe, _ = _REGISTRO[escolhida]
        _instancias[escolhida] = getattr(importlib.import_module(modulo), classe)()
        log.info("fonte ativa: %s — %s", escolhida, _instancias[escolhida].rotulo)
    return _instancias[escolhida]


def _normalizar_nome(nome: str) -> str:
    """Maiúsculas, sem acento e sem espaço sobrando, para comparar nomes."""
    sem_acento = unicodedata.normalize("NFD", (nome or "").upper())
    return " ".join(sem_acento.encode("ascii", "ignore").decode().split())


def nome_confirmado(encontrado: str | None, procurado: str | None) -> bool:
    """O nome encontrado confirma quem se procurava?

    Confirma quando os nomes são iguais ou quando toda palavra procurada
    aparece inteira no nome encontrado — "MARIA SILVA" confirma
    "MARIA APARECIDA SILVA", mas "SILVA" sozinho não, porque casaria com
    qualquer homônimo parcial. Mesma regra do selo "✓ Confirmado" da interface.
    """
    a, b = _normalizar_nome(encontrado), _normalizar_nome(procurado)
    if not a or not b:
        return False
    if a == b:
        return True
    palavras = set(a.split())
    return len(b.split()) > 1 and all(p in palavras for p in b.split())


def _rotulo(resultado: dict) -> str:
    """Traduz o resultado da fonte para o label da métrica."""
    if resultado.get("erro"):
        return "error"
    if resultado.get("cpf_inexistente"):
        return "not_registered"
    achou = resultado.get("encontrado")
    return "found" if achou is True else "not_found" if achou is False else "indeterminate"


def _consultar_medindo(ativa: Fonte, cpf_limpo: str) -> dict:
    """Consulta contando tempo e resultado.

    Fica aqui, e não dentro de cada fonte, para que toda fonte seja medida do
    mesmo jeito e com o mesmo label `fonte` — sem depender de cada
    implementação lembrar de instrumentar.
    """
    t0 = time.time()
    try:
        resultado = ativa.consultar(cpf_limpo)
    except Exception:
        _m.consulta_queries_total.labels(fonte=ativa.nome, result="error").inc()
        _m.consulta_duration_seconds.labels(fonte=ativa.nome).observe(time.time() - t0)
        raise
    _m.consulta_queries_total.labels(fonte=ativa.nome, result=_rotulo(resultado)).inc()
    _m.consulta_duration_seconds.labels(fonte=ativa.nome).observe(time.time() - t0)
    return resultado


def consultar(cpf_limpo: str, fonte: str | None = None) -> dict:
    """Consulta um CPF na fonte ativa."""
    ativa = get_fonte(fonte)
    return _consultar_medindo(ativa, cpf_limpo)


def consultar_multiplos(
    cpfs: list[str],
    nome_filtro: str | None = None,
    workers: int | None = None,
    progress_cb=None,
    match_cb=None,
    fonte: str | None = None,
    parar_ao_confirmar: bool = True,
) -> dict:
    """Consulta vários CPFs em paralelo na fonte ativa.

    Agnóstico de fonte: o paralelismo, o filtro por nome e o relatório de
    progresso valem para qualquer implementação de `Fonte`. Limites de conexão
    específicos do serviço (semáforo, rate limit) ficam dentro da própria fonte.
    """
    ativa = get_fonte(fonte)
    n_workers = max(1, min(workers if workers is not None else _cfg.DEFAULT_WORKERS, _cfg.MAX_WORKERS))
    filtro = nome_filtro.lower() if nome_filtro else None

    resultados = {}
    matches = {}
    completed = 0
    interrompido = False
    t0 = time.time()
    # em lotes grandes, loga progresso a cada ~10% para a busca não ficar muda
    passo = max(1, len(cpfs) // 10)

    log.info("lote iniciado: fonte=%s, %d cpf(s), %d workers%s",
             ativa.nome, len(cpfs), n_workers, f", filtrando nome={nome_filtro!r}" if filtro else "")
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(_consultar_medindo, ativa, cpf): cpf for cpf in cpfs}
        for future in as_completed(futures):
            if interrompido:
                break
            cpf = futures[future]
            try:
                result = future.result(timeout=_cfg.TASK_TIMEOUT)
                resultados[cpf] = result
                is_match = (
                    filtro in (result.get("nome_certidao") or "").lower()
                    if filtro else result.get("encontrado") is True
                )
                if is_match:
                    matches[cpf] = result
                    log.info("MATCH cpf=%s", mascarar_cpf(cpf))
                    # o nome da certidão é PII: só aparece em DEBUG, nunca no log padrão
                    if result.get("nome_certidao"):
                        log.debug("MATCH cpf=%s nome=%r", mascarar_cpf(cpf), result["nome_certidao"])
                    if match_cb:
                        match_cb(result)
                    # Achou quem se procurava: varrer o resto só gasta consulta
                    # no serviço externo e tempo do usuário.
                    if parar_ao_confirmar and nome_confirmado(
                        result.get("nome_certidao"), nome_filtro
                    ):
                        interrompido = True
                        canceladas = sum(1 for f in futures if f.cancel())
                        log.info("nome confirmado em %d/%d — %d consultas canceladas",
                                 completed + 1, len(cpfs), canceladas)
            except FutureTimeout:
                log.warning("timeout de %.0fs cpf=%s", _cfg.TASK_TIMEOUT, mascarar_cpf(cpf))
                resultados[cpf] = {"cpf": formatar(cpf), "encontrado": None, "erro": f"Timeout após {_cfg.TASK_TIMEOUT}s"}
            except Exception as e:
                log.warning("falha cpf=%s: %s: %s", mascarar_cpf(cpf), type(e).__name__, e)
                resultados[cpf] = {"cpf": formatar(cpf), "encontrado": None, "erro": str(e)}
            completed += 1
            if completed % passo == 0 or completed == len(cpfs):
                log.info("lote %d/%d (%d%%) — %d match(es) até agora",
                         completed, len(cpfs), completed * 100 // len(cpfs), len(matches))
            if progress_cb:
                progress_cb(completed, len(cpfs))

    log.info("lote concluído: fonte=%s, %d de %d cpf(s), %d match(es) em %.1fs%s",
             ativa.nome, completed, len(cpfs), len(matches), time.time() - t0,
             " (interrompido)" if interrompido else "")
    return {
        "total": len(cpfs),
        "consultados": completed,
        "interrompido": interrompido,
        "matches": matches,
        "resultados": resultados,
    }
