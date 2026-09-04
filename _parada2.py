import io


def sub(path, pairs, todos=False):
    s = io.open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, path + ': NAO ACHEI -> ' + old[:70]
        s = s.replace(old, new) if todos else s.replace(old, new, 1)
    io.open(path, 'w', encoding='utf-8').write(s)
    print('ok:', path)


CAMPO = ('    parar_ao_confirmar: bool = Field(default=True, description='
         '"Interrompe a busca assim que um resultado confirma o `nome` informado, '
         'em vez de varrer todos os candidatos. Sem `nome`, não tem efeito")\n')

# ── REST ───────────────────────────────────────────────────────────────
sub('app/routers/consulta.py', [
    # campo nos dois requests que aceitam nome
    ('''    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas para consulta ao TRT3 (1–{_cfg.MAX_WORKERS})")


class FeitosMultiplosRequest''',
     '''    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas para consulta ao TRT3 (1–{_cfg.MAX_WORKERS})")
''' + CAMPO + '''

class FeitosMultiplosRequest'''),
    ('''    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas para consulta ao TRT3 (1–{_cfg.MAX_WORKERS})")


router = APIRouter()''',
     '''    workers: int = Field(default=_cfg.DEFAULT_WORKERS, ge=1, le=_cfg.MAX_WORKERS, description=f"Threads paralelas para consulta ao TRT3 (1–{_cfg.MAX_WORKERS})")
''' + CAMPO + '''

router = APIRouter()'''),
])

# repassa o parâmetro nas 4 chamadas (máscara e variações, normal e stream)
s = io.open('app/routers/consulta.py', encoding='utf-8').read()
s = s.replace('consultar_multiplos, candidates, body.nome, body.workers',
              'consultar_multiplos, candidates, body.nome, body.workers,\n        parar_ao_confirmar=body.parar_ao_confirmar')
s = s.replace('consultar_multiplos(candidates, body.nome, body.workers, progress_cb=on_progress, match_cb=on_match)',
              'consultar_multiplos(candidates, body.nome, body.workers,\n                                        progress_cb=on_progress, match_cb=on_match,\n                                        parar_ao_confirmar=body.parar_ao_confirmar)')
io.open('app/routers/consulta.py', 'w', encoding='utf-8').write(s)
print('ok: chamadas do router')

# ── MCP ────────────────────────────────────────────────────────────────
sub('app/mcp_server.py', [
    ('async def find_cpf_by_mask(mascara: str, nome: str | None = None, workers: int = 8) -> dict:',
     'async def find_cpf_by_mask(mascara: str, nome: str | None = None, workers: int = 8,\n'
     '                           parar_ao_confirmar: bool = True) -> dict:'),
    ("        workers: número de threads paralelas (padrão 8)\n    \"\"\"\n    workers = max(1, min(workers, 20))\n    try:\n        candidates = gerar_cpfs_de_mascara(mascara)",
     "        workers: número de threads paralelas (padrão 8)\n"
     "        parar_ao_confirmar: interrompe assim que um resultado confirmar o 'nome' informado,\n"
     "            em vez de varrer todos os candidatos (padrão True; sem 'nome' não tem efeito)\n"
     "    \"\"\"\n    workers = max(1, min(workers, 20))\n    try:\n        candidates = gerar_cpfs_de_mascara(mascara)"),
    ('async def find_cpf_by_variations(cpf_parcial: str, nome: str | None = None, workers: int = 8) -> dict:',
     'async def find_cpf_by_variations(cpf_parcial: str, nome: str | None = None, workers: int = 8,\n'
     '                                 parar_ao_confirmar: bool = True) -> dict:'),
    ("        workers: número de threads paralelas (padrão 8)\n    \"\"\"\n    workers = max(1, min(workers, 20))\n    from app.services.cpf import generate_valid_variations",
     "        workers: número de threads paralelas (padrão 8)\n"
     "        parar_ao_confirmar: interrompe assim que um resultado confirmar o 'nome' informado\n"
     "    \"\"\"\n    workers = max(1, min(workers, 20))\n    from app.services.cpf import generate_valid_variations"),
    ('resultado = await run_in_threadpool(consultar_multiplos, candidates, nome, workers)',
     'resultado = await run_in_threadpool(consultar_multiplos, candidates, nome, workers,\n'
     '                                        parar_ao_confirmar=parar_ao_confirmar)'),
    ('''    resultado = await run_in_threadpool(
        consultar_multiplos, list(candidates), nome, workers
    )''',
     '''    resultado = await run_in_threadpool(
        consultar_multiplos, list(candidates), nome, workers,
        parar_ao_confirmar=parar_ao_confirmar,
    )'''),
])

# ── interface: mostra que parou cedo ───────────────────────────────────
sub('app/routers/ui.py', [
    ('''          inexistentes = contaInexistentes(finalData);''',
     '''          inexistentes = contaInexistentes(finalData);
          consultados  = finalData.consultados ?? totalCandidatos;
          interrompido = !!finalData.interrompido;'''),
    ('''            inexistentes = contaInexistentes(vfinal);''',
     '''            inexistentes = contaInexistentes(vfinal);
            consultados  = vfinal.consultados ?? totalCandidatos;
            interrompido = !!vfinal.interrompido;'''),
    ('''      let inexistentes = 0;      // quantos assim numa busca em lote''',
     '''      let inexistentes = 0;      // quantos assim numa busca em lote
      let consultados = 0;       // quantos candidatos chegaram a ser consultados
      let interrompido = false;  // parou cedo por ter confirmado o nome'''),
    ("""          doneStep(s4, txtResolvidos(totalCandidatos));
          inexistentes = contaInexistentes(finalData);""",
     """          doneStep(s4, txtResolvidos(finalData.consultados ?? totalCandidatos));
          inexistentes = contaInexistentes(finalData);"""),
    ("""            doneStep(s4, txtResolvidos(totalCandidatos));
            inexistentes = contaInexistentes(vfinal);""",
     """            doneStep(s4, txtResolvidos(vfinal.consultados ?? totalCandidatos));
            inexistentes = contaInexistentes(vfinal);"""),
    ("""          ? `${resultados.length} resultado${resultados.length!==1?'s':''} · ${totalCandidatos} candidatos${inexistentes ? ` · ${inexistentes} inexistentes` : ''} · ${$el.textContent}`""",
     """          ? `${resultados.length} resultado${resultados.length!==1?'s':''} · ${interrompido ? `${consultados} de ${totalCandidatos} testados — nome confirmado` : `${totalCandidatos} candidatos`}${inexistentes ? ` · ${inexistentes} inexistentes` : ''} · ${$el.textContent}`"""),
])
