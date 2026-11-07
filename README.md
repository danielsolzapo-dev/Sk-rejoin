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
