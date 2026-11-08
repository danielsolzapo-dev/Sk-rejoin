# Validação do refinamento compacto — 0.12.0

## Validado automaticamente

- `tests/test_ui_tokens.py`: contraste WCAG AA >= 4,5:1 de texto, texto secundário, destaque, sucesso, aviso, erro e informação sobre fundo, superfície, lista alternada, campo e seleção, nos dois temas. Persistência isolada e ordenação de gravações das preferências; larguras manuais preservadas no JSON.
- Ícones com a mesma geometria rasterizada em 16/20/24/32 px (RGBA); sem ampliar um bitmap de 16 px para 200%.
- `tests/test_ui_refinement.py`: prioridade semântica dos estados, ícone/texto/cor, pluralização, tabela com 100 contas, colunas por conteúdo e Estado flexível, rolagem horizontal condicional, duas linhas de rodapé, chips focáveis e visíveis, mensagem transitória e limpeza, cinco destinos clicáveis e completamente contidos no painel. Executado em Windows nos temas claro/escuro e escalas Tk 100/125/150/200.
- `tests/test_ui_workspace.py` e `tests/test_visual.py`: criação/fechamento, alternância de tema, atualização diferencial sem reescrever linhas idênticas, seleção preservada, ordenação/filtro, validação, importação mascarada, desfazer e abertura de diálogos/configurações.
- Testes funcionais preexistentes de autenticação, abertura, reconexão, sessões, BLOCK ACC, perfis e integração continuam obrigatórios e usam sessões/dados sintéticos. Nenhuma conta real é acessada nos testes.
- Compilação do EXE pelo GitHub Actions no Windows.

## Capturas reproduzíveis

`python scripts/capture_ui.py --label before` e `--label after` geram `docs/screenshots/` e o artefato `SK-UI-Screenshots`: before/after × dark/light × 100/150, principal, perfil, seções de Config e diálogos. `comparison.png` reúne as oito vistas principais.

A base visual anterior é a prévia 0.12.0 congelada em `docs/ui-before/`, usada em processos de captura isolados. Esses arquivos não entram no EXE. A antiga base 0.11.8 permanece arquivada em `docs/desktop-before.py`, mas não é usada por esta comparação.

As imagens são capturas de widgets nativos em um desktop Windows com contas fictícias. A escala é simulada pelo Tk: **não certifica o DPI de um monitor físico**. Popups de menus nativos não são abertos automaticamente porque podem bloquear a captura.

## Verificação manual no Windows

- DPI físico 100/125/150/200%, mover entre monitores com escalas diferentes e mudança do tema do Windows. Conferir nitidez de texto/arte, foco e ausência de cortes.
- Navegação por Tab/Shift+Tab, atalhos, menus, estados hover/pressionado/desabilitado e tooltips dos botões. Chips devem abrir por clique, Enter e Espaço.
- Arrastar/redimensionar/reordenar/ocultar colunas, rolar, restaurar a seleção e reabrir o APP para conferir larguras salvas.
- Verificar textos de status muito extensos, conta selecionada, erro de Place ID, remoção/desfazer e destinos recentes no tamanho mínimo da janela.
- Gestos e notificações da bandeja e execução com sessões próprias. Não enviar cookies/tickets em diagnóstico ou captura.
- Medir inicialização completa do EXE no PC de destino; tempo de construir widgets no runner não equivale ao tempo de abrir o aplicativo.

## Escopo e limites

A UI mantém a lógica e os formatos de contas, perfis e sessões. Preferências visuais ficam no `sk-ui.json` separado; larguras manuais são armazenadas em unidades lógicas para adaptação de escala. Não há nova dependência de tema: ttk/Tk próprios preservam a densidade; botões usam o mesmo contorno plano, altura, padding e estados.

Estado absorve o espaço restante. Colunas extras abertas, larguras manuais grandes ou valores arbitrariamente longos podem exceder a largura disponível: tooltip só quando o texto medido ultrapassa a célula, e rolagem somente quando há conteúdo horizontal excedente. A composição padrão de 784 px foi verificada com dados sintéticos.

Etapas são estritamente derivadas dos dados já fornecidos pelo serviço. “Etapa não informada” é usada quando não há confirmação; não são inventados sucesso de sessão/ticket/protocolo nem durações. Um destino recente apenas preenche o campo, sem iniciar o jogo. A revisão não altera autenticação, abertura, heartbeat, reconexão, BLOCK ACC, Tracker ou instalação de atualizações.
