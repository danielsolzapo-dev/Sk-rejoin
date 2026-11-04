# SK Rejoin

Aplicativo separado para gerenciar suas próprias sessões Roblox no Windows x64.

1. Extraia o ZIP em uma pasta e abra **SK Rejoin.exe**. Esse iniciador precisa do Python 3 com o launcher `pyw.exe`. A interface abre em uma janela própria do Windows. Se a versão anterior estiver rodando, encerre-a pelo botão **Encerrar app** antes de abrir esta edição.
2. Abra o app antes do Roblox para reservar o modo de múltiplas instâncias. A compatibilidade depende do cliente Roblox e precisa ser conferida no Windows.
3. Em **Importar contas**, cole uma sessão .ROBLOSECURITY por linha. O app valida no Roblox e salva as sessões protegidas pelo Windows, em `%LOCALAPPDATA%/RejoinDesk`.
4. Informe o Place ID e clique em **Abrir selecionadas**. O Windows abre o cliente Roblox instalado.
5. Em **Heartbeat**, copie o script para os clientes com suporte a HTTP local. O painel identifica cada conta pelos sinais recebidos. A reconexão é opcional, vale para a execução atual e faz até três tentativas com intervalo de 60 segundos após perder o sinal de uma conta que já esteve online.

## Executável autônomo e GitHub

No Windows, execute **Compilar-EXE.bat** para gerar `dist/RejoinDesk.exe` com o Python embutido. Para distribuir, coloque os arquivos desta pasta na raiz de um repositório separado. O fluxo Windows em `.github/workflows/release.yml` gera um artefato manualmente ou publica um release ao enviar a tag `v0.3.0`. Para novas versões, atualize `VERSION` em `update.py` e crie a tag correspondente.

O botão **Atualizações** verifica o release do repositório indicado. A edição autônoma pode verificar tamanho e SHA-256, instalar a versão e reiniciar pelo painel. A versão anterior fica com sufixo `.previous`. Use um repositório de distribuição que você controla.


## Fila, janela e bandeja

O limite conta processos Roblox abertos no PC, inclusive fora do app. A fila espera uma vaga, tenta identificar o novo processo, solicita o tamanho escolhido e aguarda um heartbeat de nova sessão da conta no Place ID solicitado. Se a abertura ficar ambígua ou o sinal faltar, a fila para. Use **Cancelar fila** para parar os próximos lançamentos.

O tamanho inicial solicitado é 320 × 240 px da janela externa. O histórico mostra a medida retornada pelo Windows, que pode impor dimensões mínimas.

Na edição com Python instalado, execute **Instalar-bandeja.bat** para habilitar o ícone perto do relógio. Fechar a janela recolhe o painel quando a bandeja está ativa. Use **Encerrar** para sair. A edição autônoma inclui essas dependências.
