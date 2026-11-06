# SK Rejoin

Aplicativo Windows x64 para suas sessões Roblox. Baixe `RejoinDesk.exe` em Releases. O app consulta atualizações do GitHub ao iniciar, verifica tamanho e SHA-256 e reinicia quando há versão nova.

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
