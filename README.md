# siga

Bot que vigia o **SIGA** (<https://siga.marcacaodeatendimento.pt>) e, quando aparece um horário que
cumpre os teus filtros, **avisa por Telegram** ou **faz a marcação sozinho**: escolhe o horário,
preenche o formulário, passa o reCAPTCHA, lê o PIN que chega ao Gmail e confirma. O comprovativo
vai por Telegram.

> **Uso pessoal.** Serve para marcar *o teu* atendimento. Não uses para reservar vagas em massa nem
> para outras pessoas sem autorização. O bot **não contorna o CAPTCHA**: clica no checkbox como uma
> pessoa e, se o Google pedir o desafio de imagens, **és tu** que o resolves (noVNC, secção 5).

## 1. Como funciona

```
 a cada `frequency` minutos, por pesquisa (watch.py)
        │
        ▼
 bot.py (Playwright/Chromium)
   Iniciar → entidade → tema/subtema/motivo/nº de casos → Presencial
   → distrito/localidade/local → página de horários
        │
        ▼
 filtros: max_days, slot_start..slot_end  ── nenhum ──► espera
        │
        ├─ auto_book: false ──► Telegram: "Horários disponíveis" (sem repetir o mesmo aviso)
        │
        └─ auto_book: true  (e DRY_RUN=0)
             urgency escolhe o horário → Marcar → formulário (dados.json)
             → reCAPTCHA: clique; desafio de imagens? Telegram + noVNC e tu resolves
             → popup "Código de validação": pin.py lê o PIN no Gmail (IMAP)
               (falhou? pede-te o PIN por Telegram) → Confirmar
             → página "Detalhes da marcação" → Telegram com captura de ecrã
```

Salvaguardas: `DRY_RUN=1` por omissão; depois de uma marcação nenhuma outra é feita
(`STOP_AFTER_BOOKING`); após `MAX_ATTEMPTS` falhas o `auto_book` dessa pesquisa desliga-se (continua
a avisar); cada falha manda uma captura de ecrã; o token do Telegram nunca vai para os logs.

## 2. Instalação (Docker)

Requisitos: Docker + Compose v2.24+, ~2 GB de RAM, conta Gmail e conta Telegram.

```bash
git clone https://github.com/lugustavo/siga && cd siga
cp .env.example .env
cp config/dados.example.json config/dados.json
```

1. **Telegram**: cria o bot com @BotFather (`/newbot`), põe o token em `BOT_TOKEN`. O `BOT_CHAT_ID`
   vê-se em `https://api.telegram.org/bot<TOKEN>/getUpdates` depois de lhe enviares uma mensagem.
2. **Gmail (PIN)**: ativa a verificação em 2 passos e o IMAP (Definições → Reencaminhamento e
   POP/IMAP), gera uma *palavra-passe de aplicação* em <https://myaccount.google.com/apppasswords> e
   põe `IMAP_USER` / `IMAP_PASSWORD` no `.env`. O endereço tem de ser o do teu `dados.json`.
3. **Dados**: edita `config/dados.json` (ver 4.2).
4. **Pesquisas**: edita `search_config.yaml` (ver 4.1).
5. **noVNC**: define `VNC_PASSWORD` (só os 8 primeiros caracteres contam) e `NOVNC_URL`
   (`http://IP-DO-SERVIDOR:6080/vnc.html?autoconnect=1&resize=scale`).

```bash
docker compose up -d --build
docker logs -f siga
```

Sem Docker: `pip install -r requirements.txt && playwright install chromium`, depois
`python watch.py` (corre sem janela; em Linux sem `DISPLAY` o browser é headless).

## 3. Testar antes de depender dele

Por esta ordem, com o local de teste (Óbidos, que já vem no `search_config.yaml`):

**Sem Docker** (mais simples; o browser corre sem janela e não há noVNC, por isso um desafio de
imagens do CAPTCHA não pode ser resolvido):

```bash
python bot.py --search "CC Obidos (teste)" --dry-run 1               # 1) so le os horarios (nao clica em Marcar)
python bot.py --search "CC Obidos (teste)" --dry-run 2 --auto-book   # 2) clica em Marcar e preenche o formulario, sem CAPTCHA nem submissao
python bot.py --search "CC Obidos (teste)" --dry-run 0 --auto-book   # 3) marca a serio: cria uma marcacao real; cancela-a logo a seguir em "Consultar marcações"
```

**Com Docker e noVNC** (para poderes resolver o desafio de imagens): sobe o contentor e corre o bot
*dentro* dele, que é onde está o ecrã virtual que o noVNC mostra:

```bash
docker compose up -d --build
docker compose exec siga python bot.py --search "CC Obidos (teste)" --dry-run 0 --auto-book
```

Abre `http://IP-DO-SERVIDOR:6080/vnc.html` (com `NOVNC_BIND` definido, ver 5) para ver o browser do bot.

Nos níveis 2 e 0 o bot usa `config/dados.json`, e só faz algo se a pesquisa tiver `auto_book: true`.
`--auto-book` liga isso só nessa execução, sem editar o `search_config.yaml`. Sem ele (e com
`auto_book: false`) o bot recusa e diz porquê, em vez de ler os horários e parar em silêncio.

## 4. Configuração

### 4.1 `search_config.yaml`

Uma lista de blocos `- search:`. Os valores de entidade, assunto e local são **o texto que vês no
site** (sem distinguir acentos/maiúsculas) ou o **id numérico** da opção.

| Campo | Por omissão | Descrição |
|---|---|---|
| `title` | `Pesquisa N` | Nome (aparece nos avisos e no estado). Tem de ser único. |
| `auto_book` | `false` | `false` = só avisa; `true` = marca sozinho (ver `DRY_RUN`). |
| `entity_opt` | – | Entidade, ex. `IRN Registo`. |
| `service_opt.tema/subtema/motivo` | – | Assunto, ex. `Cidadão` / `Cartão de Cidadão - Pedido/Renovação` / `Pedido/Renovação de Cartão de Cidadão`. |
| `service_opt.qtd_casos` | `1` | Número de casos a tratar (1 a 5). |
| `location_opt.distrito/localidade` | – | Ex. `Lisboa` / `Sintra`. |
| `location_opt.local_atendimento` | – | Ex. `CRC Sintra`. |
| `max_days` | `90` | Só conta horários dentro destes dias (1 a 90). |
| `slot_start` / `slot_end` | `00:00` / `23:59` | Janela horária aceite para o atendimento. |
| `urgency` | `MAX` | Que horário escolher entre os válidos: `MAX` o mais cedo, `MED` o do meio, `MIN` o mais tarde. |
| `frequency` | `5` | Minutos entre verificações (2 a 120), mais um jitter de até 30 s. |
| `start_time` / `end_time` | `07:00` / `23:59` | Horas do dia em que a pesquisa corre. |

O site só mostra as **sugestões mais próximas**; o bot lê essas (o mesmo que a página "Horário da
marcação"), não o calendário "Escolher outra data mais conveniente".

### 4.2 `config/dados.json`

| Campo | Descrição |
|---|---|
| `nome` | Nome completo (máx. 100). |
| `tipo_identificacao` | `CC`, `NIS`, `BI`, `NIF`, `PA` ou `AR`. |
| `numero` | Número do documento (CC: 12 caracteres, ex. `123456789ZZ0`). |
| `email` | Onde chega o PIN: tem de ser o do `IMAP_USER`. |
| `telemovel` | 9 dígitos, começa por 91, 92, 93 ou 96. Obrigatório email **ou** telemóvel. |
| `telefone` | Opcional (9 dígitos). |

O ficheiro é validado no arranque com as mesmas regras do site.

### 4.3 `.env`

Ver `.env.example`. As principais: `DRY_RUN` (1 = só ler, 2 = preencher sem submeter, 0 = marcar),
`STOP_AFTER_BOOKING`, `MAX_ATTEMPTS`, `CAPTCHA_WAIT_S`, `VNC_PASSWORD`, `NOVNC_URL`, `NOVNC_BIND`,
`IMAP_*`, `PIN_TIMEOUT_S`. Depois de alterar o `.env` ou o `search_config.yaml`:
`docker compose up -d --force-recreate`.

## 5. O CAPTCHA e o noVNC

O formulário tem um reCAPTCHA v2 (checkbox). O bot clica nele; muitas vezes passa sozinho. Se o
Google pedir o **desafio de imagens**, o bot manda um Telegram com o `NOVNC_URL` e espera até
`CAPTCHA_WAIT_S` segundos (300 por omissão). Abres o link, resolves o desafio no browser do
contentor, e o bot continua sozinho (o próprio site submete o formulário quando o CAPTCHA é validado).
Se não resolveres a tempo, conta como uma falha de marcação.

**Segurança do noVNC**: dá controlo de um browser com os teus dados. Por omissão a porta só abre em
`127.0.0.1`; para a LAN ou Tailscale define `NOVNC_BIND=<ip da máquina>`. Nunca a exponhas à
internet e usa uma `VNC_PASSWORD` própria. Num servidor remoto, o mais simples é um túnel SSH:
`ssh -L 6080:127.0.0.1:6080 servidor`.

O PIN tem **5 minutos** (o popup mostra a contagem): IMAP (`PIN_TIMEOUT_S`, 240 s) mais o fallback
por Telegram cabem nesse limite.

## 6. Operação

```bash
docker logs -f siga                        # ver o que esta a fazer
docker compose up -d --force-recreate      # aplicar alteracoes
docker compose stop                        # parar
cat data/state.json                        # booked / tentativas / ultimo aviso
rm data/state.json                         # recomecar
ls data/shots/                             # capturas (.png) e HTML de cada falha
```

`data/shots/` guarda capturas e HTML das falhas, **com os teus dados pessoais**: apaga-as quando já
não precisares e tapa-as ao pedires ajuda. Nunca ponhas no git: `.env`, `config/dados.json`, `data/`.

## 7. Resolução de problemas

| Sintoma | Causa provável |
|---|---|
| `opcao 'X' nao existe em #IdLocalidade: [...]` | O texto não existe na lista do site (a mensagem mostra as opções); corrige o `search_config.yaml`. |
| `sem horarios que cumpram os filtros` | Normal. Há horários na página mas fora de `max_days` / `slot_start..slot_end`, ou o SIGA não tem nenhum. |
| `login IMAP` / `IMAP falhou` | IMAP desligado, 2 passos desligados, ou app password errada (16 caracteres, sem espaços). O bot pede o PIN por Telegram. |
| `PinRejected` | Código errado ou expirado; a mensagem do site vem na exceção. |
| `CaptchaTimeout` | Desafio de imagens não resolvido a tempo, ou `NOVNC_URL`/`VNC_PASSWORD` por configurar. |
| `o popup do formulario nao abriu` | Alguém levou o horário, ou o site mudou. Vê `data/shots/*-erro.png`. |
| noVNC pede a palavra-passe e recusa (`password check failed`) | A `VNC_PASSWORD` do `.env` é outra, ou mudaste o `.env` sem recriar: `docker compose up -d --force-recreate`. Só contam os 8 primeiros caracteres. Evita `$` e `#` na palavra-passe. |
| noVNC liga mas o ecrã está preto | Normal: o browser só aparece durante uma verificação ou marcação **dentro do contentor**. Um `python bot.py` corrido fora do Docker não aparece no noVNC. |
| O link do Telegram tem `&amp;` | Só nos logs (o texto vai escapado). No Telegram aparece `&`. Se copiares do log, troca `&amp;` por `&`. |
| noVNC nem abre a página | `NOVNC_BIND` por omissão é `127.0.0.1`: define o IP da máquina (ex. `192.168.2.153`) e recria o contentor. |
| O bot parou de marcar | `MAX_ATTEMPTS` atingido ou `booked` em `data/state.json`; apaga-o para recomeçar. |

## 8. Estrutura

```
watch.py           loop de vigilancia, estado, avisos
bot.py             fluxo no browser (Playwright)
slots.py           ler/filtrar/escolher horarios (funcoes puras)
config.py          validacao de search_config.yaml e dados.json
pin.py             PIN: IMAP (Gmail) -> fallback Telegram
notify.py          Telegram
entrypoint.sh      Xvfb + noVNC + watch.py
tests/             pytest (unitarios + passos do popup em paginas locais, sem rede)
```

Testes: `pip install -r requirements-dev.txt && python -m pytest -q tests`.

## 9. Notas técnicas do site

- É ASP.NET MVC (jQuery): `/Marcacao/MarcacaoInicio` → `Entidades` → `Assunto` → `Local` → `HorarioLocal`.
- Entidade: `button.btn-selecionar-entidade` (o `id` é o id da entidade; ex. IRN Registo = 176).
  Assunto: `#IdCategoria`, `#IdSubcategoria`, `#IdMotivo`, `#NumCasos`, `#btnOpcoesAtendimento`; depois
  `presencialSelecionarLocalAtendimento()`. Local: `#IdDistrito`, `#IdLocalidade`, `#IdLocalAtendimento`.
- Horários: `a.set-appointment` com `onclick="guardaDadosDoSlot(idMesa,idLocal,"2026-11-30T14:15:00",…)"`.
- Popup `#ModalDadosCliente` (`#NomeCliente`, `#TipoIdentificacao`, `#NumeroIdentificacao`,
  `#EmailCliente`, `#TelemovelCliente`, `#TelefoneCliente`); o `#recapcha` só aparece com o
  formulário válido, e o callback do CAPTCHA submete o formulário.
- O servidor devolve a página com o popup `#ModalCodigo` (`#btn_confirmToken`, erro em
  `#lbl_erro_codigo`, endpoint `/Marcacao/ValidaToken`). O email vem de `siga@marcacaodeatendimento.pt`,
  assunto *Código de Validação*, com um código de 5 dígitos em HTML (`O seu código de validação é: <b>56131</b>`).
- Confirmação: página "Detalhes da marcação" com o *Código de Marcação*.
