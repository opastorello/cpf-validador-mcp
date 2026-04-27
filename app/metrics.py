from prometheus_client import Counter, Histogram, Gauge

# ── TRT3 scraping ──────────────────────────────────────────────────────────────

trt3_queries_total = Counter(
    "trt3_queries_total",
    "Consultas individuais ao TRT3 por resultado (1 por CPF consultado)",
    ["result"],  # found | not_found | indeterminate | error
)

trt3_captcha_attempts_total = Counter(
    "trt3_captcha_attempts_total",
    "Tentativas de resolução de CAPTCHA (cada retry = 1)",
)

trt3_captcha_result_total = Counter(
    "trt3_captcha_result_total",
    "Resultado de cada tentativa de CAPTCHA",
    ["result"],  # success | wrong | error
)

trt3_captcha_duration_seconds = Histogram(
    "trt3_captcha_duration_seconds",
    "Tempo para baixar e resolver o CAPTCHA",
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0],
)

trt3_query_duration_seconds = Histogram(
    "trt3_query_duration_seconds",
    "Tempo total de uma consulta ao TRT3 (inclui todas as tentativas de CAPTCHA)",
    buckets=[2, 5, 10, 20, 30, 60, 120, 300],
)

trt3_captcha_retries_per_query = Histogram(
    "trt3_captcha_retries_per_query",
    "Número de tentativas de CAPTCHA necessárias por consulta",
    buckets=[1, 2, 3, 5, 10, 15, 20],
)

trt3_concurrent_queries = Gauge(
    "trt3_concurrent_queries",
    "Consultas TRT3 em execução agora (inclui as aguardando semáforo)",
)

trt3_pdf_parsed_total = Counter(
    "trt3_pdf_parsed_total",
    "PDFs de certidão baixados e processados",
    ["result"],  # success | error
)

trt3_session_resets_total = Counter(
    "trt3_session_resets_total",
    "Resets de sessão HTTP por causa de erro ou CAPTCHA errado",
    ["reason"],  # wrong_captcha | exception
)

trt3_http_errors_total = Counter(
    "trt3_http_errors_total",
    "Erros HTTP ao se comunicar com o TRT3",
    ["type"],  # timeout | connection | http_status
)

# ── CPF operações ──────────────────────────────────────────────────────────────

cpf_validations_total = Counter(
    "cpf_validations_total",
    "Validações matemáticas de CPF",
    ["result"],  # valid | invalid
)

cpf_variations_generated_total = Counter(
    "cpf_variations_generated_total",
    "Total de variações de CPF geradas pelo endpoint /cpf/variations",
)

cpf_mask_searches_total = Counter(
    "cpf_mask_searches_total",
    "Buscas por máscara iniciadas",
)

cpf_mask_candidates_total = Counter(
    "cpf_mask_candidates_total",
    "Total de candidatos gerados por buscas de máscara",
)

cpf_variation_searches_total = Counter(
    "cpf_variation_searches_total",
    "Buscas por variações de CPF parcial/errado iniciadas",
)

cpf_variation_candidates_total = Counter(
    "cpf_variation_candidates_total",
    "Total de candidatos gerados por buscas de variações",
)

cpf_bulk_queries_total = Counter(
    "cpf_bulk_queries_total",
    "Chamadas ao endpoint /trt3/feitos-multiplos",
)

cpf_bulk_size = Histogram(
    "cpf_bulk_size",
    "Quantidade de CPFs por chamada ao /trt3/feitos-multiplos",
    buckets=[1, 2, 5, 10, 20, 50, 100],
)

cpf_bulk_invalid_total = Counter(
    "cpf_bulk_invalid_total",
    "CPFs inválidos rejeitados em chamadas bulk (formato ou dígitos verificadores)",
)

# ── Resultados por endpoint ────────────────────────────────────────────────────

trt3_feitos_total = Counter(
    "trt3_feitos_total",
    "Consultas ao /trt3/feitos por resultado",
    ["result"],  # found | not_found | error
)

trt3_matches_total = Counter(
    "trt3_matches_total",
    "CPFs encontrados (matched) por tipo de busca",
    ["type"],  # feitos | multiplos | mascara | variacoes | mcp_feitos | mcp_multiplos | mcp_mascara | mcp_variacoes
)

# ── Acesso / uso ───────────────────────────────────────────────────────────────

trt3_rate_limit_total = Counter(
    "trt3_rate_limit_total",
    "Requisições bloqueadas por rate limit por endpoint",
    ["endpoint"],
)

trt3_mcp_calls_total = Counter(
    "trt3_mcp_calls_total",
    "Chamadas recebidas via MCP por ferramenta e resultado",
    ["tool", "result"],
    # tool: validate_cpf|generate_valid_variations|check_feitos_trabalhistas|
    #       find_cpf_by_mask|find_cpf_by_variations|check_multiple_cpfs
    # result: success|not_found|invalid|error
)
