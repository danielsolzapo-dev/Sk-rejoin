# Plano de execução da especificação

Estado honesto: auditoria e primeira base de confiabilidade em PR. **Não é entrega de todas as fases. Não é correção confirmada do 403.**

## Entregue nesta PR

- [x] Leitura integral e comparação de hashes com a base GitHub.
- [x] Auditoria antes das alterações; evidências e linhas da base.
- [x] Backup/recuperação JSON, temporário único e recusa de corrupção sem backup.
- [x] Prazo para espera de vaga e erro explícito após falha de compactação.
- [x] Redação compartilhada em histórico/diagnóstico/retorno de erros.
- [x] Diagnóstico copiável e atualização de linhas por diferença.
- [x] Testes de falha/corrida/cancelamento; smoke de 100 contas no Windows.
- [x] CI de PR; publicação somente por tag; build sem permissão de escrita.
- [x] Roteiro manual e arquitetura documentados.

## Fase 1 restante

- [ ] Identificar causa e validar resgate do ticket no cliente real.
- [ ] Máquina de estados única com transições, timeout global e cancelamento completo.
- [ ] Backoff com jitter; relógio e cache de rede diagnosticados por tentativa.
- [ ] Schema versionado/migrações por domínio; fixtures 0.5; recuperação amigável antes da criação da UI.
- [ ] Heartbeat versionado, intervalo/backoff e validação completa do payload.
- [ ] Tipos de flags; atualização com retry/retomada/healthcheck/rollback e agenda de operações.

## Fase 2 restante

- [ ] Catálogo completo de logs/exceções e crash handler; testes de todos os emissores.
- [ ] Rate limit e tokens por cliente/execução; porta configurável compatível com Tracker.
- [ ] Protocolo HMAC versionado e migração conjunta com Tracker.
- [ ] Dependências fixadas/auditadas, Dependabot, lint de segurança e metadados do EXE.
- [ ] Decisão sobre certificado de assinatura e licença pelo mantenedor.
- [ ] Aviso de termos no primeiro uso; eventual exportação criptografada.

## Fases 4, 3, 5 e 6 restantes, nessa ordem

- [ ] Pacote src/skrejoin por camadas, shims, type hints, lint/mypy e logging com rotação.
- [ ] Tema claro/escuro, tokens, DPI, assistente, acessibilidade, catálogos pt-BR/en.
- [ ] Ordenação/colunas persistidas, atalhos completos, Config com busca, tray agregado.
- [ ] pytest e cobertura >=80% do core; build e inicialização real do EXE no CI.
- [ ] Medições CPU/RAM com 1/5/20 contas.
- [ ] README reescrito, CHANGELOG, SECURITY, CONTRIBUTING, templates e metadados.
- [ ] Candidata por tag e execução do roteiro Windows/Roblox; só depois release estável.
