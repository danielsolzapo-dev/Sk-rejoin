# Validação do Revamp visual 2

## Automatizada

- tests/test_ui_tokens.py calcula WCAG AA >=4,5:1 dos tokens textuais nos fundos usados, tema escuro e claro; persistência de preferências isolada.
- Testes funcionais preexistentes continuam obrigatórios. Os testes de UI rodam no Windows; Linux não certifica Tk Windows.
- scripts/capture_ui.py gera antes/depois da principal, perfil, Config e todos os diálogos alterados; matriz escuro/claro e escala Tk 100/150. Usa contas fictícias, não abre navegadores/jogos nem usa sessões reais.
- A cópia docs/desktop-before.py corresponde à base 0.11.8 e serve somente para comparação visual. Não participa da aplicação.
- Capturas são salvas em docs/screenshots e como artefato SK-UI-Screenshots.

## Manual obrigatória

- Escalas reais Windows 100/125/150/200%, troca entre monitores e mudança de tema do Windows. Verificar foco, ícones, texto, menus e rolagem sem cortes.
- Ícone e gestos nativos da bandeja; notificações opcionais e comportamento ao fechar/minimizar.
- Tempo de abertura deve ser medido no EXE no PC de destino; não declarar menos de 1 segundo sem medição.
- Conferir login/importação com contas próprias, manter CAPTCHA/2FA oficiais; verificar que nenhum valor sensível aparece em log/captura.
- Após alteração de campos em Config, conferir salvar/cancelar e aviso de alterações pendentes. Reset de campos não aplica flags nem altera inicialização até a ação existente de Salvar/Aplicar.
- A abertura que retorna 403 é um problema funcional preexistente e permanece fora desta revisão visual.

## Limites da entrega

O catálogo pt-BR cobre textos de apresentação; textos retornados pelo backend são exibidos sem reescrever o protocolo. Inglês é opcional e ainda não oferecido. Tempos de sessão/ticket/protocolo não são inventados: o backend atual não fornece uma linha do tempo com essas durações. Animações novas não são usadas. CustomTkinter/sv-ttk não foram adicionados: ttk próprio preserva densidade e não acrescenta dependência de tema ao EXE.
