# SK Rejoin

Aplicativo Windows x64 para suas sessões Roblox. Baixe `RejoinDesk.exe` em Releases. O app consulta atualizações do GitHub ao iniciar, verifica tamanho e SHA-256 e reinicia quando há versão nova.

## 0.7.1

A aba Config tem rolagem para acessar os controles em janelas pequenas.

**Otimizar** abre Config → Desempenho e BLOCK ACC. Escolha a pasta que contém RobloxPlayerBeta.exe usada pelo WebLauncher ou deixe vazio para detectar a instalação registrada. Feche os Roblox e aplique o perfil econômico. Ele solicita texturas mínimas, MSAA 1x, qualidade de renderização 1, grama e distâncias CSG reduzidas e teto de FPS escolhido (padrão 10).

A aceitação dessas flags depende do cliente. O app modifica o ClientAppSettings.json da instalação selecionada. Configurações internas próprias do executável WebLauncher não têm uma API documentada e são ajustadas na janela da ferramenta. Quando a pasta da versão do Roblox mudar, selecione a nova instalação para reaplicar o perfil.

O backup guarda os valores anteriores das flags afetadas. Restaurar anterior recupera essas chaves na última instalação otimizada e preserva as demais chaves. Reaplicar o perfil mantém o backup original. O modo econômico do app recolhe o banner e atualiza a interface a cada 4 segundos, mantendo o heartbeat independente.

**BLOCK ACC** é opcional e vem desligado. Quando ativado, aberturas e reconexões selecionam servidores públicos diferentes para as contas acompanhadas pelo mesmo SK Rejoin neste PC. A seleção usa o JobId completo, reservas temporárias e a lista pública do Roblox. Falha de consulta, ausência de servidor ou heartbeat antigo interrompem a abertura em vez de escolher um servidor aleatório.

Atualize o script em Heartbeat e no Auto Execute de cada cliente. A coluna Servidor mostra o início do JobId ou Atualizar HB. O heartbeat detecta colisões após entradas externas ou teletransportes e solicita que a conta que chegou depois vá a outro servidor. Se não houver destino disponível, essa conta é desconectada para interromper a disputa. A janela pode continuar aberta e exigir revisão manual. O script precisa executar novamente depois de cada entrada/teleporte.

Esta coordenação é local ao app e não separa contas de outros PCs, apps ou clientes sem heartbeat. A lista de servidores pode mudar entre consulta e entrada. Os testes cobrem escolha e reserva concorrentes, colisão, indisponibilidade, restauração e interface Windows. Teleporte e comportamento das flags em um Roblox real precisam de validação nos seus PCs.

## 0.6.0

- A fila usa o limite configurado mesmo quando a reserva interna do modo multi não está disponível. O aviso aparece em Config e no histórico. Um novo processo junto da instância anterior confirma que múltiplos processos foram observados, e o heartbeat confirma cada conta.
- Config é uma aba separada. Downgrade / WebLauncher permite consultar a versão publicada em vnnaworks/weblauncher, baixar o executável com tamanho e SHA-256 fornecidos pelo GitHub, escolher um .exe existente e abrir a ferramenta.
- A escolha da versão e o downgrade são realizados na janela do WebLauncher. O repositório distribui executáveis e não fornece fonte ou uma API documentada para automatizar essa etapa dentro do SK Rejoin.
- Após configurar a ferramenta, o SK Rejoin continua usando a associação do protocolo Roblox no Windows. Não há garantia de compatibilidade entre versões do cliente, launchers e múltiplas instâncias.
- O download fica neste PC e só é aberto por um clique explícito em Abrir WebLauncher. Feche os jogos antes de trocar a versão.

## 0.5.0

- Diagnóstico de abertura na barra superior, com estado do Windows, protocolo Roblox, processos e modo multi-instância.
- Tempo sem heartbeat entre 10 e 3600 segundos e de 1 a 20 tentativas por conta. A espera entre tentativas dobra até 1 hora e começa após cada tentativa terminar. A contagem zera após 2 minutos de heartbeat contínuo.
- Selecione uma conta para carregar suas preferências. Informe destino e parâmetros e clique Ativar reconexão. Pausar selecionadas afeta apenas a seleção. Usar destinos salvos por conta permite abrir um lote nos destinos individuais.
- Preferências e tentativas ficam neste usuário Windows. Ao reiniciar o app, o monitoramento aguarda um novo heartbeat antes de agir. Reiniciar o app não abre contas automaticamente.
- Compacto recolhe o banner. A tabela mostra tempo conectado observado, último sinal e tentativa de reconexão.
- A instância iniciada é identificada por PID e criação. Se ainda estiver aberta sem heartbeat, o app pede para conferir o coletor e não admite uma duplicata dessa instância.

Abra o SK Rejoin antes do Roblox para reservar o modo multi-instância. Configure o limite de janelas. Adicione contas por cookie ou Nick e senha. A janela oficial do Chrome permite concluir pessoalmente CAPTCHA e 2FA. Sessões são validadas e protegidas pelo Windows no cofre local. Senhas do lote não são persistidas.

Em Heartbeat, copie o coletor para cada cliente com HTTP local. Após uma nova abertura, o coletor precisa executar novamente para confirmar a conta. O limite de FPS usa ClientAppSettings e aplica na próxima abertura do Roblox. A compatibilidade depende do cliente instalado.

O GitHub Actions compila e publica a versão declarada em update.py. Testes de reconexão e API usam processos simulados. Valide abertura, permissões e multi-instância nos seus PCs Windows.



## Versão 0.8.0

- Config > Inicialização: iniciar o .exe ao entrar no Windows e abrir um aplicativo adicional escolhido por arquivo. Salve as opções e mantenha o Rejoin em uma pasta fixa. Não grava senha do Windows. Um aplicativo adicional já aberto é reconhecido pelo caminho.
- Contas > Salvar perfil selecionadas: destino, dimensões, FPS, tempo sem sinal e tentativas. O FPS individual depende de setfpscap disponível no ambiente do coletor.
- Reconectar selecionadas encerra somente o PID/tempo de criação vinculado e abre a conta novamente. Sem vínculo seguro, a operação informa que a janela precisa ser fechada manualmente.
- Recuperação automática dos erros 279/773 requer reconexão ativada e Heartbeat atualizado que consiga ler o diálogo do Roblox. Falhas antes de o coletor executar não têm código identificado por este mecanismo. Mantém teto de tentativas e espera progressiva.
- Detalhes da conexão mostra servidor atual, conflito, destino e espera do BLOCK ACC.
- Tracker 3.19.0: na aba Gerenciador, estados do SK Rejoin e pedidos de rejoin local ou remoto. Execute ambos no mesmo usuário Windows em cada PC e atualize os agentes. O acesso de controle usa chave local de sessão separada, limitada a estado e rejoin; cookies e senhas não são enviados ao Tracker. Pedidos remotos expiram e não são repetidos após uma tentativa de execução.
- Substitua o Heartbeat no Auto Execute após atualizar.

## Versão 0.8.1 — Ordem de inicialização

Em Config > Inicialização, configure Rejoin → WebLauncher → Executor → Contas. Escolha o WebLauncher em sua aba, selecione o executor e ajuste as esperas (10 e 20 segundos por padrão, até 180 segundos). Os intervalos não verificam se um executor concluiu sua preparação interna.

Selecione as contas na aba Contas, salve seus perfis com Place ID e depois use Usar contas selecionadas na aba Contas, dentro de Config > Inicialização. Marque Abrir contas selecionadas, salve e use Testar sequência salva. A sequência é executada a cada abertura do Rejoin. Contas já vinculadas ou com heartbeat recente são ignoradas.

Iniciar com Windows registra o Rejoin para seu usuário. A ordem é garantida dentro da sequência do Rejoin; o Windows agenda outros programas de inicialização independentemente. Uma etapa que falha interrompe a sequência e informa o motivo no painel e no histórico. Cancelar sequência interrompe as esperas; Cancelar fila interrompe aberturas de contas já enviadas. Nenhuma elevação de privilégios adicional é aplicada.

## Versão 0.9.0 — Revamp visual

Nova navegação lateral, cabeçalho compacto com a arte SK, indicadores maiores e tabela com linhas alternadas. Busca por nick/ID e filtros por estado só mudam a visualização. Linhas escondidas pelos filtros são removidas da seleção para impedir ações em contas ocultas. Duplo clique abre os detalhes da conexão.

Abrir e Reconectar ficam no topo do painel de execução. Há barra horizontal na tabela e rolagem nos diálogos. A janela inicial respeita o tamanho do monitor. Todas as configurações, perfis, sessões e inicialização existentes são preservadas. Nenhuma mudança na rotina de abertura, BLOCK ACC ou reconexão nesta versão.

## Versão 0.10.0 — SK Control / Tracker 3.20.0

Na aba Gerenciador do Tracker, o painel SK Control mostra cada PC, o estado dos programas e suas contas salvas no SK Rejoin. A seleção e os comandos ficam presos ao computador escolhido. Quando o Tracker tem dados do mesmo UserId nesse PC, a conta mostra também nível, mar e atualização do coletor.

Comandos disponíveis: preparar PC usando a sequência salva, abrir, reconectar, fechar, aplicar perfil (incluindo ativar/pausar reconexão), diagnóstico, verificar atualização e instalar atualização do APP pelo GitHub. Abrir e reconectar usam os destinos salvos por conta; salve o Place ID primeiro. Preparar usa os executáveis e as contas configurados localmente na aba Inicialização. O painel não recebe cookies e não permite escolher comandos executáveis arbitrários remotamente.

Recebido, executando, concluído, falhou ou resultado incerto são estados separados. Abrir/reconectar exige uma sessão nova confirmada pelo Heartbeat. Fechar exige o PID e o tempo de criação vinculados localmente e pausa a reconexão das contas fechadas. A preparação confirma a execução da sequência e a entrega das contas à fila; a conexão de cada conta continua visível separadamente.

Pedidos expiram, ficam registrados antes da execução e não são reaplicados após reinício sem confirmação. Um resultado incerto requer conferir o PC antes de solicitar novamente. A instalação de atualização confirma o envio ao atualizador; a versão exibida após o reinício confirma a instalação efetiva. Não feche o APP durante a instalação.

Execute Tracker e SK Rejoin no mesmo usuário Windows em cada PC. Atualize também os agentes do Tracker. O APP precisa estar aberto para receber comandos; ligar o PC remotamente não faz parte desta integração.

## Versão 0.11.0 — Interface clássica de contas

Interface organizada no estilo do Roblox Account Manager: lista de contas à esquerda, destino e ações à direita, adicionar/remover na barra inferior e menus Contas, Utilitários, Exibir e Configurações. A identidade permanece SK Rejoin.

Adicionar conta abre as opções Nick e senha ou Importar cookies. Clique direito na lista oferece entrar, reconectar, copiar nick/UserId, detalhes e remover. Exibir permite mostrar servidor e tentativas, alterar altura das linhas e recolher os controles. Busca, filtros e seleção múltipla permanecem disponíveis. Config mantém inicialização, WebLauncher e BLOCK ACC.

Esta atualização reorganiza a interface. Não implementa Refresh Cookie nem altera as sessões armazenadas, a autenticação, os comandos do Tracker ou a rotina de abertura dos jogos.

## Versão 0.11.1 — Janela compacta

A janela principal usa 784 × 301 pixels de área de conteúdo, com linhas de 20 pixels. A lista fica à esquerda e o painel de entrada à direita, como no formato compacto do Roblox Account Manager. A moldura e a escala de exibição do Windows acrescentam dimensões externas.

Perfil/reconexão e Configurações abrem em janelas separadas, preservando o tamanho da janela principal. Busca e filtros ficam em Utilitários > Buscar / filtrar (Ctrl+F). Servidor e tentativas podem ser exibidos pelo mesmo menu. O APP continua redimensionável.

## Versão 0.11.2 — Adicionar contas

O botão Adicionar conta abre o login manual. A seta ao lado oferece Login manual, Nick e senha (User:Pass) e Cookies. Não há opção Custom. O menu pertence ao próprio botão da seta para postagem correta no Tk/Windows.

Login manual abre um navegador isolado em www.roblox.com/login. Entre na conta e conclua as verificações solicitadas. A sessão só é salva depois de ser validada pelo Roblox. Usa Chrome e tenta Edge se o Chrome não abrir.

User:Pass permite preencher até 6 contas ou colar nick:senha, uma por linha. Senhas que contêm dois-pontos são preservadas. Até 3 janelas são abertas em paralelo. Os campos são limpos ao iniciar ou fechar a importação. Cookies mantém a importação existente, uma sessão por linha.

A captura usa apenas a sessão do contexto de login aberto pelo APP e o User-Agent desse navegador. A sessão continua protegida pelo Windows no PC local. Nenhum cookie é enviado ao Tracker.

## Versão 0.11.3 — User:Pass em campo único

A opção Nick e senha (User:Pass) agora abre diretamente um único campo de texto. Cole nick:senha, uma conta por linha. O APP reconhece e conta as linhas válidas automaticamente. Senhas com dois-pontos continuam preservadas. Permanecem o limite de 6 contas por lote e até 3 navegadores simultâneos. Os dados digitados são limpos ao iniciar ou fechar a importação.
