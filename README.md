# Transcritor Jornalístico

[English](README.en.md) | **Português (Brasil)**

Ferramenta local para transcrever arquivos de áudio e vídeo com
[whisper.cpp](https://github.com/ggml-org/whisper.cpp), acelerar a transcrição em GPU AMD por
Vulkan, separar vozes com
[pyannote.audio Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
e produzir TXT, JSON e SRT. Nenhum arquivo de mídia é enviado a uma API de transcrição.

> Esta V1 separa vozes como `SPEAKER_00`, `SPEAKER_01` etc. Ela não reconhece o nome real
> das pessoas.

## Arquitetura

```text
mídia original (nunca alterada)
  -> FFprobe + FFmpeg (WAV PCM 16-bit, mono, 16 kHz)
  -> whisper-cli compilado com Vulkan (texto e timestamps)
  -> pyannote.audio em CPU (intervalos de falantes)
  -> alinhamento por maior sobreposição temporal
  -> TXT + JSON + SRT, gravados atomicamente
```

O Python apenas orquestra ferramentas locais. A transcrição e a diarização são módulos
independentes, o que permite trocar um backend no futuro sem reescrever os exportadores.

## Requisitos

- Windows 10/11 de 64 bits;
- Python 3.11 ou 3.12 de 64 bits (3.11 é a recomendação conservadora);
- Git;
- FFmpeg e FFprobe no `PATH`;
- driver AMD atualizado, com Vulkan;
- para compilar whisper.cpp: Visual Studio 2022 Build Tools com “Desenvolvimento para
  desktop com C++”, CMake e Vulkan SDK;
- espaço em disco para os modelos. `large-v3` ocupa vários gigabytes;
- internet somente para instalar dependências e baixar os modelos inicialmente.

O FFmpeg, whisper.cpp, CMake e o Vulkan SDK não são pacotes Python e não estão em
`requirements.txt`.

## Preparando o Python e a `.venv`

Instale o Python pelo [site oficial](https://www.python.org/downloads/windows/) e marque a
opção para adicioná-lo ao `PATH`. Em um novo PowerShell, na raiz deste projeto:

```powershell
python --version
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Para desenvolver e executar os testes:

```powershell
pip install -r requirements-dev.txt
pytest -q
```

## Instalando FFmpeg

Instale uma distribuição de FFmpeg para Windows e adicione sua pasta `bin` ao `PATH`.
Feche e reabra o PowerShell e confirme:

```powershell
ffmpeg -version
ffprobe -version
```

Também é possível usar `winget` se o pacote estiver disponível na sua instalação:

```powershell
winget search ffmpeg
winget install --id Gyan.FFmpeg.Shared
```

O identificador do pacote pode mudar; valide o resultado de `winget search` antes de
instalar. Nesta máquina, FFmpeg e FFprobe já foram encontrados no `PATH`.

## Compilando whisper.cpp com Vulkan

O projeto oficial documenta a opção CMake `GGML_VULKAN`. Os binários comuns de release
para Windows podem não incluir Vulkan, portanto a compilação local é o caminho mais
previsível para a RX 6600.

### 1. Pré-requisitos da compilação

Instale:

1. [Git](https://git-scm.com/download/win);
2. [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/),
   incluindo MSVC e Windows SDK;
3. [CMake](https://cmake.org/download/), adicionando-o ao `PATH`;
4. [LunarG Vulkan SDK](https://vulkan.lunarg.com/sdk/home#windows).

Reinicie o terminal e confirme:

```powershell
git --version
cmake --version
vulkaninfo --summary
```

### 2. Compilação

Use o “Developer PowerShell for VS 2022”:

```powershell
Set-Location $env:USERPROFILE\Documents
git clone https://github.com/ggml-org/whisper.cpp.git
Set-Location .\whisper.cpp

cmake -B build -DGGML_VULKAN=ON -DGGML_CUDA=OFF -DGGML_HIP=OFF
cmake --build build --config Release --parallel
```

Copie o executável e as DLLs produzidas para este projeto. Ajuste o segundo caminho para
a pasta real do repositório:

```powershell
$DestinoWhisper = "C:\caminho\para\Transcrição_whisper\bin\whisper"
New-Item -ItemType Directory -Force $DestinoWhisper
Copy-Item .\build\bin\Release\* $DestinoWhisper
```

O arquivo esperado pela configuração padrão é:

```text
bin/whisper/whisper-cli.exe
```

Se o executável estiver em outro lugar, altere `whisper.executable` em `config.yaml`.
Não é necessário passar uma opção Vulkan em cada transcrição: o backend faz parte do
binário compilado. A aplicação usa `-ng` somente quando `use_gpu: false`.

### 3. Confirmando Vulkan

Execute o binário diretamente. O log inicial deve identificar o backend Vulkan e a GPU;
uma compilação CPU-only não fará isso.

```powershell
.\bin\whisper\whisper-cli.exe --help
.\bin\whisper\whisper-cli.exe `
  -m .\models\whisper\ggml-small.bin `
  -f .\exemplo.wav `
  -l pt
```

Procure no início da saída por informações de Vulkan/GGML e pelo dispositivo AMD. Se a
execução falhar ao carregar DLLs, copie todas as DLLs geradas ao lado do executável e
confirme que o Vulkan Runtime do driver AMD está instalado.

## Baixando um modelo Whisper

O programa nunca baixa modelos automaticamente. Os modelos devem estar no formato GGML
compatível com whisper.cpp. Para baixar manualmente pelo repositório oficial de modelos:

```powershell
New-Item -ItemType Directory -Force .\models\whisper

# Teste mais leve
Invoke-WebRequest `
  -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin" `
  -OutFile ".\models\whisper\ggml-small.bin"

# Qualidade maior; arquivo muito grande
Invoke-WebRequest `
  -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin" `
  -OutFile ".\models\whisper\ggml-large-v3.bin"
```

Defina no YAML `model: small`, `model: medium` ou `model: large-v3`. O nome é resolvido
como `models/whisper/ggml-NOME.bin`. Também é aceito um caminho `.bin` explícito. Para um
primeiro teste, `small` reduz tempo e memória; para entrevistas finais em português,
`large-v3` tende a priorizar qualidade, ao custo de processamento e memória maiores.

## Configurando pyannote

O modelo aberto `pyannote/speaker-diarization-community-1` roda localmente. O acesso
inicial exige uma conta Hugging Face, aceitação das condições na página do modelo e um
token de leitura.

1. Entre na [página do Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
   e aceite as condições;
2. crie um token de leitura em `https://huggingface.co/settings/tokens`;
3. copie `.env.example` para `.env` e preencha o token:

```powershell
Copy-Item .env.example .env
notepad .env
```

```dotenv
HF_TOKEN=hf_seu_token_real
```

`.env` está ignorado pelo Git. Nunca coloque o token em `config.yaml` nem faça commit
dele. O pipeline é carregado uma única vez e reutilizado para todo o lote.

### Uso offline após o download

Na primeira execução, o pyannote baixa os arquivos necessários para o cache do Hugging
Face. Para uma cópia explícita e portátil dentro de `models/`:

```powershell
.\.venv\Scripts\Activate.ps1
hf auth login
hf download pyannote/speaker-diarization-community-1 `
  --local-dir .\models\diarization\community-1
```

Depois, altere:

```yaml
diarization:
  local_model_path: models/diarization/community-1
  device: cpu
```

Teste desconectado, opcionalmente forçando as bibliotecas Hugging Face a não acessar a
rede durante a sessão:

```powershell
$env:HF_HUB_OFFLINE = "1"
python main.py .\exemplo.mp4 --speakers 2
Remove-Item Env:HF_HUB_OFFLINE
```

O modelo Community-1, o whisper.cpp e o FFmpeg trabalham localmente. A primeira instalação
e os downloads evidentemente usam a internet.

## Configuração

Os caminhos relativos em `config.yaml` são resolvidos a partir da localização do próprio
YAML, não do diretório atual do terminal. Não há caminhos pessoais no código.

Principais opções:

```yaml
whisper:
  executable: bin/whisper/whisper-cli.exe
  model: large-v3
  language: pt
  use_gpu: true
  gpu_backend: vulkan

diarization:
  enabled: true
  device: cpu
  min_speakers: 2
  max_speakers: 5

processing:
  recursive: false
  skip_existing: true
  keep_temp_on_error: true
```

Antes do primeiro processamento, valide tudo:

```powershell
python main.py --check
```

## Como usar

### Um arquivo

```powershell
python main.py "C:\Videos\entrevista.mp4"
```

### Uma pasta

```powershell
python main.py "C:\Videos\Entrevistas"
```

### Incluir subpastas

```powershell
python main.py "C:\Videos\Entrevistas" --recursive
```

### Número conhecido de falantes

`--speakers` sobrescreve temporariamente os limites mínimo e máximo:

```powershell
python main.py "C:\Videos\entrevista.mp4" --speakers 2
```

Ou use limites:

```powershell
python main.py "C:\Videos\entrevista.mp4" --min-speakers 2 --max-speakers 4
```

### Sem diarização, outro modelo e reprocessamento

```powershell
python main.py ".\entrevista.mp4" --no-diarization
python main.py ".\entrevista.mp4" --model medium
python main.py ".\entrevista.mp4" --force
```

Execute `python main.py --help` para a lista completa.

## Estrutura dos resultados

```text
output/
  txt/entrevista.txt
  json/entrevista.json
  srt/entrevista.srt
  manifest.json
```

Em lotes de pasta, nomes únicos permanecem legíveis. Somente quando duas mídias têm o
mesmo nome-base, elas recebem um hash determinístico do caminho relativo, evitando colisão
entre `pasta-a/entrevista.mp4` e `pasta-b/entrevista.mp4`. O manifesto guarda
status, tamanho e data de modificação do arquivo. Com `skip_existing: true`, saídas
completas do mesmo arquivo são ignoradas. Se a origem tiver mudado, ela é reprocessada.

As saídas são primeiro escritas em um arquivo temporário oculto e somente depois movidas
atomicamente para o nome final. Assim, uma interrupção não transforma um arquivo parcial
em resultado concluído.

### TXT

O TXT agrupa blocos contíguos do mesmo falante para leitura menos fragmentada:

```text
[00:00:03] SPEAKER_00
Como você avalia os dados divulgados ontem?

[00:00:09] SPEAKER_01
Nós identificamos uma diferença entre as duas bases.
```

### JSON

O JSON preserva caminho da origem, idioma, duração, modelo, texto completo e segmentos
com segundos, timestamps e falante. É adequado para `pandas` e futuras ferramentas de
renomeação. Alterar `speaker` no JSON permite trocar `SPEAKER_00` por `ENTREVISTADOR` sem
executar os modelos novamente.

### SRT

O SRT usa timestamps com milissegundos e prefixa a legenda com o identificador do falante.
Sem diarização, o prefixo é omitido.

## Estratégia de alinhamento

Para cada segmento do Whisper, o alinhador soma a duração de sobreposição de cada falante
e escolhe a maior. No exemplo em que `SPEAKER_00` ocupa 0,8 s e `SPEAKER_01` ocupa 4,2 s,
o bloco pertence a `SPEAKER_01`.

O Community-1 oferece uma diarização “exclusiva”, sem falas simultâneas, especialmente
útil para conciliar transcrição e falantes. A V1 não divide texto proporcionalmente no
meio de um segmento: o timestamp do bloco não revela com segurança o limite de cada
palavra, e uma divisão inventaria conteúdo. O backend e as estruturas permitem adotar
timestamps por palavra futuramente.

## Lotes, erros e temporários

- os arquivos são ordenados alfabeticamente pelo caminho;
- um erro é registrado e o lote continua no próximo arquivo;
- o traceback completo vai para `logs/transcritor-AAAA-MM-DD.log`, não para o terminal;
- WAVs PCM 16-bit/mono/16 kHz são usados diretamente;
- outras mídias geram um WAV em `temp/` e a origem nunca é modificada;
- temporários são apagados após sucesso;
- com `keep_temp_on_error: true`, o WAV é mantido após erro para diagnóstico;
- `Ctrl+C` limpa o temporário atual quando possível, preserva saídas finalizadas e retorna
  o código 130.

## Abrindo no VS Code

1. Abra a pasta deste projeto em **File > Open Folder**;
2. execute **Python: Select Interpreter** e selecione `.venv`;
3. abra um terminal PowerShell integrado;
4. ative com `.\.venv\Scripts\Activate.ps1`;
5. execute `python main.py --check` e depois o comando de transcrição.

## Primeiro teste

Depois de testar `whisper-cli` diretamente e configurar o pyannote:

```powershell
python main.py ".\exemplo.mp4" --speakers 2
```

Resultado esperado (o nome terá hash somente se houver outra mídia com o mesmo nome-base):

```text
output/txt/exemplo.txt
output/json/exemplo.json
output/srt/exemplo.srt
```

Para isolar problemas, comece sem diarização:

```powershell
python main.py ".\exemplo.mp4" --no-diarization --model small
```

## Solução de problemas

### `python` não é reconhecido

Instale Python 3.11/3.12 de 64 bits, habilite “Add Python to PATH” e abra um terminal novo.
Esse é o estado atual desta máquina: o projeto foi validado com o runtime de teste do
workspace, mas uma instalação normal do Python ainda é necessária para uso cotidiano.

### FFmpeg ou FFprobe não encontrado

Confirme que ambos estão na mesma pasta `bin`, que essa pasta está no `PATH` e reinicie o
VS Code. Rode `Get-Command ffmpeg` e `Get-Command ffprobe`.

### whisper.cpp ou modelo não encontrado

Confira `whisper.executable` e `paths.whisper_models`. O nome `large-v3` exige exatamente
`ggml-large-v3.bin` na pasta configurada.

### Vulkan não aparece

Atualize o driver AMD, teste `vulkaninfo --summary`, apague a pasta `build` do whisper.cpp
e recompile com `-DGGML_VULKAN=ON`. Não use uma release CPU-only por engano.

### Erro 401/403 ou modelo pyannote inacessível

Aceite as condições do Community-1 com a mesma conta do token, confirme `HF_TOKEN` no
`.env` e faça a primeira execução conectado à internet. Não publique o `.env`.

### Diarização lenta

Ela está configurada em CPU por segurança e compatibilidade com a GPU AMD. `--no-diarization`
permite validar a transcrição isoladamente. O modelo permanece carregado entre arquivos do
mesmo lote.

### Arquivo com erro interrompeu?

Erros normais de FFmpeg, whisper.cpp, pyannote ou exportação são capturados por arquivo.
O lote só encerra antecipadamente por `Ctrl+C` ou por uma falha global detectada antes do
início, como ausência do executável/modelo.

## Privacidade e versionamento

Áudio, vídeo, transcrições e modelos permanecem locais. `models/`, `bin/`, `temp/`,
`output/`, `logs/`, `.env` e `.venv/` estão no `.gitignore`; apenas arquivos `.gitkeep`
mantêm a estrutura. Revise o JSON antes de compartilhá-lo, pois ele inclui o caminho local
da mídia em `metadata.source_path`.

## Licença e créditos

Copyright 2026 Vitor Almeida.

Este projeto é distribuído sob a [Apache License 2.0](LICENSE). Ela permite uso,
modificação e distribuição, inclusive comercial, desde que os avisos de copyright,
licença e atribuição sejam preservados e as alterações sejam identificadas. Consulte
também o arquivo [NOTICE](NOTICE).
