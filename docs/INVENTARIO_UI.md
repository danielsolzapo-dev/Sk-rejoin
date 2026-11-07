# Inventário de UI antes do redesign

Base 31f3a6f / 0.11.8. app.py, desktop.py, windows.py e tray.py foram lidos; desktop.py concentra as telas. A branch visual parte de main, sem incorporar as alterações funcionais da PR de auditoria.

| Superfície | Componentes / ações existentes |
|---|---|
| Principal | Tabela com conta, estado, sinal; colunas adicionais tempo, reconexão e servidor; busca/filtro; Place ID; Entrar; Reconectar; totais e seleção |
| Adicionar | Botão Login manual; seta Login manual/User:Pass/Cookies; campo único User:Pass com contador |
| Perfil | Tempo sem sinal, tentativas, destinos individuais, limite de instâncias, dimensões, FPS, salvar/ativar/pausar/cancelar |
| Config | Desempenho e BLOCK ACC, WebLauncher e Inicialização; pasta da instalação, flags reversíveis, executor e sequência |
| Conexão | Conta, servidor, conflito, destino e intervalo BLOCK ACC |
| Autenticação | Sessão, etapa, HTTP, emissão do ticket e desafio |
| Diagnóstico | Windows, multi, processo, protocolo, proxy e tentativas de autenticação |
| Outros | Heartbeat/copiar, FPS, atualizações, histórico |
| Contexto | Entrar, reconectar, copiar nick/ID, detalhes, remover |
| Menus | Contas, Utilitários, Exibir, Configurações (objeto existente, ainda não ligado à janela) |
| Tray | Mostrar e Encerrar |

Estados textuais existentes: Pronta, Na fila, Abrindo, Aguardando heartbeat, Online, Sem sinal, Sem sessão, Carregando, Pausada, Limite de tentativas, erro com motivo e etapas BLOCK ACC (carregando/esperando/procurando/troca/sem servidor). Não existe uma máquina de estados canônica para a UI; o redesign apenas apresenta o estado recebido.

Callbacks de rede já usam workers/queue; FPS ainda grava arquivo na thread Tk e precisa ser extraído sem mudar as regras existentes. A janela inicial atual é 784×301, linhas 20px, minsize720×285. Arte em artwork/banner.png, portrait.png e sk.ico.

Capturas antes/depois são geradas por scripts/capture_ui.py com fixtures isoladas. Não contêm contas ou segredos reais. Escala Tk simulada 100/150 não substitui verificação de DPI por monitor Windows.
