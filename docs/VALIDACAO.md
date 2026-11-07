# Validação manual — candidata ainda não publicada

Pré-requisito: Windows x64; contas próprias; cópia de segurança da pasta `%LOCALAPPDATA%\RejoinDesk`; nenhuma senha/cookie/ticket nos anexos. A execução automatizada usa somente fixtures. Não desativar antivírus nem controles de segurança para testar.

## Bloqueadores da candidata

| Caso | Procedimento | Aceitação | Evidência atual |
|---|---|---|---|
| 403 | Mesma conta e Place ID no RAM e SK; usar o mesmo WebLauncher; registrar horários e logs redigidos | Login e conexão aceitos nas duas tentativas | RAM funcionou; SK retornou 403 no resgate. **Pendente** |
| Ticket | Testar autenticação, depois abrir normalmente | Ticket novo em cada abertura; teste não consome o de abertura | Simulação passou; resgate real pendente |
| Atualização | Em pasta de teste, executar versão anterior e atualizar por release | Inicia versão nova, dados preservados | Healthcheck/rollback ainda não implementados; **não aprovado** |
| Migração | Copiar fixtures de versões anteriores para perfil isolado | Dados mantidos, migrar uma e duas vezes tem resultado idêntico | Envelope/schema ainda não introduzido; compatibilidade de layouts legados testada |

## Funcionamento no Windows

1. Criar perfil isolado; abrir EXE e sair por Encerrar e bandeja. Confirmar que porta/processo são liberados.
2. Importar conta por login manual e por User:Pass. Concluir pessoalmente CAPTCHA/2FA. Cancelar durante abertura e durante espera. Não repetir com contas reais em CI.
3. Abrir uma conta; só considerar conectada após heartbeat novo. Repetir com duas instâncias e confirmar que a primeira permanece no processo correto.
4. Ativar reconexão, desconectar o jogo e observar atraso/teto; 120 segundos contínuos de heartbeat sem erro zeram tentativas.
5. Com limite de instâncias atingido, aguardar 120 segundos ou cancelar; BUSY precisa voltar a falso e a conta deve exibir motivo.
6. Fechar/reconectar apenas a conta selecionada. Não encerrar processos sem vínculo PID + tempo de criação.
7. BLOCK ACC: duas contas no mesmo servidor; personagem carregado e dez segundos de espera; conta posterior solicita teleporte, sem Kick. Validar sem destino, falha 773 e pausa.
8. Otimização: fechar jogos, registrar ClientAppSettings original, aplicar duas vezes, restaurar e comparar chaves alheias. Selecionar nova pasta quando a versão mudar. Aceitação de flags precisa ser observada no cliente.
9. Startup opt-in: verificar a ordem Rejoin → WebLauncher → aplicativo escolhido → contas e testar cancelamento nas duas esperas.
10. Integração: Tracker e APP no mesmo usuário; abrir/reconectar/fechar conta selecionada; repetir ID do pedido e reiniciar durante execução. Não executar novamente um resultado incerto.

## Dados, erros e interface

- Em perfil isolado, corromper um JSON com backup e abrir: restaurar backup, avisar no diagnóstico, manter cofre DPAPI. Não testar corrupção no perfil de produção.
- Sem backup válido, não sobrescrever arquivo nem substituir cofre por vazio. O tratamento amigável global da inicialização ainda é pendente.
- Conferir diagnóstico copiável: sem cookies, tickets, senhas, URLs autenticadas ou comandos do protocolo.
- Janela 784×301 com linhas de 20px, 100 contas, seleção múltipla e filtros; diálogos/configuração não alteram o tamanho principal.
- Testar manualmente monitores em 100%, 125% e 150%. CI ainda não certifica DPI misto.
- Medir CPU/RAM com 1/5/20 contas sem confundir consumo do APP com consumo do Roblox. Não existem medições reais anexadas.

Registrar resultado, versão/commit, Windows, escala, launcher/cliente, horário e evidência redigida. **Não marcar a revisão completa enquanto os bloqueadores estiverem pendentes.**
