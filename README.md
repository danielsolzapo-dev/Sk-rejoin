# SK Rejoin

Aplicativo Windows x64 para organizar suas contas Roblox e acompanhar sessões por Heartbeat. O layout compacto mantém os controles de entrada à direita e a lista de contas à esquerda.

## Revamp visual 2 — versão 0.12.0

O redesign foi incorporado à `main` para publicação da versão 0.12.0 pelo GitHub Releases. Mantém os serviços de autenticação, reconexão, BLOCK ACC e os formatos de sessões existentes.

### Antes e depois

![Antes: interface compacta original](docs/screenshots/before-dark-100-main.png)

![Depois: tema escuro](docs/screenshots/after-dark-100-main.png)

![Depois: tema claro](docs/screenshots/after-light-100-main.png)

As imagens mostram contas fictícias. [Matriz completa](docs/screenshots/) · [Inventário anterior](docs/INVENTARIO_UI.md) · [Validação visual](docs/VALIDACAO_VISUAL.md) · [Histórico](CHANGELOG.md).

A interface refinada tem rodapé em duas linhas, chips acessíveis, colunas automáticas, estados semânticos e destinos recentes. [Comparação completa](docs/screenshots/comparison.png). As larguras ajustadas manualmente são mantidas nas preferências visuais; a coluna Estado absorve a área restante.

## Instalação em Windows recém-formatado

O EXE inclui o interpretador Python e as bibliotecas Python da aplicação. Não é necessário instalar Python, pip, Pillow, pystray ou Playwright separadamente para executar o EXE.

| Componente | Quando usar | Download |
| --- | --- | --- |
| SK Rejoin x64 | Aplicativo | [Versão publicada](https://github.com/danielsolzapo-dev/Sk-rejoin/releases/latest/download/RejoinDesk.exe) |
| Roblox | Cliente do jogo e protocolo registrado no Windows | [Site oficial](https://www.roblox.com/download) |
| Chrome ou Edge | Login manual e User:Pass abrem um navegador instalado; Edge moderno já instalado também serve | [Chrome oficial](https://www.google.com/intl/pt-BR/chrome/) |
| Microsoft Visual C++ v14 x64 | Runtime recomendado em uma instalação limpa; útil se houver erro de DLL/runtime | [Microsoft](https://aka.ms/vc14/vc_redist.x64.exe) |
| WebLauncher | Opcional, para quem usa essa integração em Configurações | [Releases do projeto](https://github.com/vnnaworks/weblauncher/releases/latest) |

Instale o cliente Roblox e um dos navegadores. Abra o SK Rejoin, adicione suas contas e configure o destino. Para Heartbeat, copie novamente o script fornecido pelo próprio APP, com a chave desta instalação. O WebLauncher é uma ferramenta separada e não é requisito para executar a interface do SK Rejoin.

## Uso rápido

1. Baixe o [SK Rejoin para Windows x64](https://github.com/danielsolzapo-dev/Sk-rejoin/releases/latest/download/RejoinDesk.exe). O atualizador consulta as versões publicadas em GitHub Releases.
2. Use Adicionar conta para login manual oficial; a seta mantém User:Pass e Cookies. Conclua pessoalmente verificações solicitadas no navegador.
3. Selecione uma conta, informe Place ID e use Entrar. Em Heartbeat, copie o script fornecido pelo serviço e configure seu ambiente local. O sinal confirma a conexão observada pelo APP.

Exibir permite trocar tema e organizar colunas. Configurações mantém os controles de inicialização, desempenho, BLOCK ACC e WebLauncher em seções próprias. Perfil / reconexão abre uma janela separada.

Atalhos: Ctrl+N adicionar; Ctrl+F buscar; Ctrl+A selecionar contas com foco na tabela; Del remover; F5 atualizar; Ctrl+Enter abrir; Ctrl+R reconectar; Ctrl+, configurações; Ctrl+K buscar ação. Duplo clique abre detalhes e clique direito oferece ações da conta. A remoção aguarda seis segundos e pode ser desfeita antes do envio ao serviço.

Preferências de tema, colunas e destinos recentes ficam em `sk-ui.json`, separado de contas e perfis. Valores sensíveis são limpos ao iniciar ou fechar a importação. Cookies são exibidos mascarados; não os envie em diagnóstico.

## Limites conhecidos e validação

- Tema do Windows, monitores mistos, nitidez em 125%/150%/200%, atalhos/gestos da bandeja e notificações exigem conferência manual no PC. A matriz automatizada simula escala Tk de 100%/150%; não certifica todos os monitores.
- Aceitação de flags/FPS e teleporte dependem do cliente e do ambiente de Heartbeat. O redesign não muda essas regras.
- Instalação automática via GitHub consulta versões publicadas; dados existentes continuam nos mesmos arquivos. Não há migração do cofre nesta revisão visual.
- A UI pode mostrar o HTTP recebido e o último sinal; não inventa tempos por etapa que o backend não mede.
- Automação de contas pode contrariar os termos da plataforma. Esta UI não implementa evasão, CAPTCHA solver ou garantia contra penalidades.
