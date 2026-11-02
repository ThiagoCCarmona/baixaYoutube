# BaixaYoutube

Baixa vídeos do YouTube em **MP3** ou **MP4** — por uma janela moderna (tema claro/escuro) ou pelo terminal.
Atualiza-se sozinho e se protege contra atualizações quebradas.

## Instalação (usuários)

Baixe o `BaixaYoutube-Setup-<versão>.exe` em **[Releases](../../releases/latest)** e execute.
Não precisa de Python nem de permissão de administrador.

> O instalador ainda não tem assinatura digital, então o Windows pode mostrar
> "O Windows protegeu o computador". Clique em **Mais informações → Executar assim mesmo**.

### Recursos

- MP3 (192 kbps) ou MP4
- MP4 **compatível** (H.264 + AAC, até 1080p, abre em qualquer player) ou **qualidade máxima** (até 4K/8K, VP9/AV1)
- Nome do arquivo opcional (padrão: título do vídeo) e escolha da pasta
- Atualização automática do app e do motor de download

## Como as atualizações funcionam

| Camada | O que faz | Quando |
|---|---|---|
| **App** | Ao abrir, consulta o último release no GitHub. Se houver versão nova, mostra "Atualizar agora": baixa o instalador, confere o SHA-256, instala em modo silencioso e reabre o app. | A cada abertura |
| **Motor (yt-dlp)** | Baixa o yt-dlp mais novo do PyPI (SHA-256 conferido), **valida em outro processo** com uma consulta real ao YouTube e só então ativa — sem reinstalar e sem reiniciar. | A cada 6 h, em segundo plano |
| **Volta automática** | Se um download falhar com o motor atualizado e ele não passar mais na validação, o app volta à versão anterior (ou à embutida), marca a quebrada como rejeitada e tenta o download de novo. | Na hora da falha |
| **Release automático** | O workflow *Atualiza yt-dlp* confere o PyPI todo dia; se houver versão nova, fixa-a, roda os testes, gera o instalador e publica um release. | Diariamente (GitHub Actions) |

Falhas de rede nunca rejeitam uma versão: se o motor atual também falha na validação, o problema é a
conexão ou o YouTube, e nada é alterado.

Arquivos do usuário ficam em `%APPDATA%\baixa\` (`config.json`, `baixa.log`, `atualizacoes.json`, `motor\`).

## Desenvolvimento

```
pip install -r requirements-build.txt
pip install -e . --no-deps
python -m pytest              # testes offline
python -m pytest -m rede      # valida o motor contra o YouTube de verdade
```

Requer Python 3.10+ (o executável é gerado com 3.14).

### Estrutura

```
baixa/nucleo.py        lógica de download (sem interface) — reaproveitável
baixa/atualizador.py   atualização do app e do motor, validação e volta automática
baixa/gui.py           interface (CustomTkinter)
baixa/cli.py           comando de terminal "baixa"
build/                 spec do PyInstaller, ícone e ponto de entrada do .exe
instalador/baixa.iss   instalador (Inno Setup 6)
scripts/versao.py      versão do app e pin do yt-dlp
.github/workflows/     CI, release e atualização diária do yt-dlp
```

### Terminal

```
baixa <link> <mp3|mp4> [-o PASTA] [-n NOME] [-q compativel|max]
```

```
baixa "https://www.youtube.com/watch?v=jNQXAC9IVRw" mp3 -n "minha musica"
baixa "https://youtu.be/aqz-KE-bpKQ" mp4 -q max -o C:\Users\voce\Videos
```

Interface gráfica pelo Python: `baixa-gui`.

### Gerar o executável localmente

Requer Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

```
.\build.ps1
```

Gera `dist\BaixaYoutube\BaixaYoutube.exe` e `dist\BaixaYoutube-Setup-<versão>.exe`.

Modos do executável sem janela (usados pelo CI e pelo atualizador):

| Comando | Faz |
|---|---|
| `BaixaYoutube.exe --verificar ARQ` | checagem offline: imports, extratores, ffmpeg |
| `BaixaYoutube.exe --autoteste PASTA` | baixa um vídeo curto em MP3 e MP4 |
| `BaixaYoutube.exe --atualizar-motor ARQ` | procura, valida e ativa um yt-dlp mais novo agora |
| `BaixaYoutube.exe --validar-motor PASTA` | valida um motor baixado (vazio = o embutido) |

Defina `BAIXA_DADOS=C:\alguma\pasta` para testar sem tocar nos dados reais do usuário.

### Publicar uma versão

```
python scripts/versao.py definir 0.5.0
git commit -am "Versão 0.5.0"
git tag v0.5.0
git push origin main v0.5.0
```

O workflow **Release** testa, gera o instalador e publica o release com `SHA256SUMS.txt`.
Versões só de yt-dlp são publicadas sozinhas pelo workflow **Atualiza yt-dlp**.

## Viabilidade como app mobile

| Item | Situação |
|---|---|
| Interface (CustomTkinter) | Não roda em Android/iOS; a tela teria de ser refeita (ex.: Flet ou Kivy). |
| `baixa/nucleo.py` + yt-dlp | Reaproveitáveis: yt-dlp é Python puro e roda no Android. |
| ffmpeg | Principal bloqueio: sem ele não há MP3 nem MP4 em HD. |
| Alternativa robusta | App nativo em Kotlin com a biblioteca `youtubedl-android` (como Seal e YTDLnis). |
| Distribuição | Google Play não aceita apps que baixam do YouTube; só APK. iOS: inviável. |

## Aviso legal

Use apenas para baixar conteúdo que você tem direito de baixar (seus próprios vídeos, conteúdo em
domínio público ou com licença que permita). Respeite os Termos de Serviço do YouTube e os direitos autorais.

Licença: [MIT](LICENSE).
