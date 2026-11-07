# Auditoria técnica — SK Rejoin 0.11.8

Base: `31f3a6f7088573ff3ac47aab5d7fd604c96677db`, 7 de novembro de 2026. Leitura integral dos módulos, scripts, testes, workflow, README e manifesto; inventário de formato/dimensão dos três recursos de artwork. Os hashes Git dos arquivos locais foram comparados com a árvore remota: nenhuma divergência. Nenhum cofre real, cookie ou senha foi consultado.

## Resultado

O projeto NÃO atende ainda à definição de pronto da especificação. O 403 no resgate é confirmado por logs reais e permanece sem causa identificada. Testes simulados verdes não demonstram abertura/autenticação real. Não publicar outra correção do 403 sem evidência.

## Arquitetura atual

- `app.py` (918 linhas): servidor HTTP, rotas, fila, estados globais, reconexão, perfis, inicialização, integração e entrada Tk.
- `desktop.py` (1.042 linhas): Tk compacto, clientes HTTP em workers, diálogos, importação e parte de acesso a registro/disco para FPS.
- `accounts.py`: JSON, DPAPI, identidade Roblox, ticket, protocolo e mutex.
- `windows.py`: enumeração de processos/janelas, criação do PID, fechamento vinculado.
- `bridge_commands.py`: allowlist, expiração, recibos persistentes e serialização do trabalho.
- `bootstrapper.py`: download verificado e execução do WebLauncher selecionado. Não contém o código do WebLauncher nem implementa seu downgrade.
- `startup.py`, `tray.py`, `optimization.py`, `server_picker.py`, `browser_login.py`, `update.py`: serviços auxiliares.
- `heartbeat.luau`: request HTTP local, FPS opcional e teleporte de colisões.
- `.github/workflows/release.yml`: testes Windows, PyInstaller onefile e publicação em main/tags.

## Achados com evidência

As linhas abaixo se referem à base auditada, antes das correções.

| ID | Prioridade | Evidência | Consequência / ação |
|---|---|---|---|
| A01 | Crítica | accounts.py:125–187; tests/test_auth_flow.py | Emissão/handoff não verificam resgate. Logs do SK: 403 em `/v1/authentication-ticket/redeem`; RAM: resposta web login e conexão aceita na mesma instalação. Causa desconhecida; manter teste real como bloqueador de release estável. |
| A02 | Alta | accounts.py:14–19 | JSON inválido é substituído por default em memória. Uma escrita posterior pode sobrescrever as contas percebidas como vazias. Não há backup válido nem aviso. |
| A03 | Alta | accounts.py:18–19 | Nome temporário fixo por destino. Escritas de módulos com locks distintos podem colidir. Substituição atômica não resolve concorrência do temporário. |
| A04 | Alta | app.py:324–328 | Espera por limite de instâncias sem timeout total. Há cancelamento, mas a fila pode ficar ocupada indefinidamente. |
| A05 | Alta | app.py:339–427 | Falhas em compactação/identificação após abrir podem sair pelo except externo e deixar status Abrindo. finally só limpa Na fila/Limite. |
| A06 | Alta | update.py:61–70 | `.previous` existe, porém não há confirmação de inicialização, rollback automático, retry de download ou retomada. Não é recuperação transacional de atualização. |
| A07 | Alta | app.py:817–826, 884–915 | /install verifica BUSY, mas não a sequência de startup; /exit encerra servidor sem necessariamente fechar Tk. Shutdown e operações críticas precisam coordenador único. |
| A08 | Média | app.py:21–22, 572–589 | Bind loopback, Host/Origin e chaves existem. KEY heartbeat é persistente e compartilhada; faltam versão, rate limit e rejeição de números JSON não finitos. |
| A09 | Média | bridge_commands.py:26–73 | Allowlist, ID e expiração existem. Não há HMAC por pedido. Recibos limitados a 200 não equivalem a anti-replay eterno. Mudança precisa protocolo compatível com Tracker. |
| A10 | Média | desktop.py:819–872 | FPS acessa registro e disco na thread Tk; UI ainda mistura lógica de infraestrutura. |
| A11 | Média | desktop.py:477–503 | Mesmo quando dados não mudam, toda linha recebe item(values/tags); busca move linhas a cada atualização. Colunas sem ordenação/persistência. |
| A12 | Média | requirements.txt; workflow:4,39 | Versões não fixadas; ausência de auditoria de dependências, lint/tipos/cobertura e inicialização do EXE. Push em main publica estável sem teste real. |
| A13 | Média | heartbeat.luau:1–100 | Intervalo fixo; sem versão no payload ou backoff de transporte; JSONEncode fora do pcall(send). Mensagem Atualizar HB usa ausência de jobId, não versão. |
| A14 | Média | accounts.py:113; app.py:117; desktop.py:440 | Mensagens têm sanitizações locais, mas não há redação central no limite de logs, diagnósticos e exceções. Não alegar garantia de ausência de segredos. |
| A15 | Média | optimization.py:53–104 | Backup seletivo existe e testes preservam flags alheias. Tipos/chaves de arquivos externos não são validados integralmente; troca de pasta de versão exige orientação. |
| A16 | Baixa | README.md | Histórico e instruções se contradizem (kick, banner, abas e modo compacto). Faltam documentos de arquitetura, validação, contribuição e segurança. |

## launcher.s

Arquivo textual Assembly x64 em sintaxe AT&T/GNU. Localiza a pasta do próprio executável e chama ShellExecuteW para `pyw.exe` com `-3 app.py`. Importa GetModuleFileNameW, ExitProcess, ShellExecuteW e MessageBoxW. Usa RVAs de tabela de imports com valor fixo, logo seu build depende de layout não documentado. Não há referência a ele no workflow ou Compilar-EXE.bat. A extensão `.s` é válida para Assembly; não é evidência de malware. Tratamento: conservar por compatibilidade, identificar como legado e documentar; não renomear/remover antes de confirmar usos externos. O build suportado é PyInstaller.

## Segurança existente a preservar

DPAPI por usuário Windows; senhas de lote em memória; importação oficial em contextos isolados; endpoints de autenticação fixos; redirects recusados; API loopback com chaves distintas; controle remoto sem cookies; allowlist de comandos; fechamento com PID e tempo de criação; SHA-256 e tamanho dos downloads; flags reversíveis.

## Riscos e limites

- Não existe ambiente Windows/Roblox autenticado neste executor. CI Windows disponível com dados sintéticos; log do usuário é evidência real apenas da tentativa registrada.
- Não é possível reproduzir resgate real sem cliente/conta autorizada no PC de teste; não pedir cookies para isso.
- Assinatura de código depende de certificado do mantenedor. Não inventar assinatura ou adicionar chave ao repositório.
- Não escolher uma licença de distribuição em nome do titular sem decisão explícita.
- Envelope/schema de todos os arquivos, HMAC e troca de pacote exigem migração compatível com consumidores externos; mudança global apressada pode quebrar o Tracker.
- Automação de contas pode contrariar regras da plataforma. Não implementar evasão, CAPTCHA solver ou prometer ausência de penalidades.

## Sequência de execução e aceitação

1. Fixar a base e adicionar testes de caracterização, sem modificar a autenticação por hipótese.
2. Corrigir A02/A03/A04/A05 com testes de falha/corrida/cancelamento; diagnóstico exportável redigido.
3. Introduzir máquina de estados e schema/migrações por domínio, com fixtures antigas; manter chaves externas durante transição.
4. Versionar handshake e protocolo Tracker antes de exigir novos campos/HMAC.
5. Melhorar atualização (healthcheck/rollback), infraestrutura HTTP, dependências e logging central.
6. Migrar progressivamente para `src/skrejoin/` preservando entrypoints/imports de compatibilidade.
7. Melhorar UI com 784×301 e linhas 20px, smoke 100 contas/DPI, temas/catálogos.
8. Completar documentação, segurança CI, métricas/cobertura >=80% do core; publicar candidata por tag.
9. Só considerar 403 resolvido após abertura real confirmada na mesma conta/PC que funcionam com RAM.

Cada fase deve ter commits pequenos e PR; status pendente deve continuar explícito.
