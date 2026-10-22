# Shadow of the Colossus — PC (port nativo / native port) · v0.59.1-linux.3

**[Español](#español)** · **[Português](#português)** · **[English](#english)** · [Releases](../../releases) · [Changelog](CHANGELOG.md)

> **Nenhum arquivo do jogo nem da Sony está incluído / No game or Sony files are included.**
> Você precisa do seu próprio dump do jogo e, para ter som, de dois módulos do seu próprio
> console. / You need your own game dump and, for sound, two modules from your own console.
> Este projeto não tem ligação com a Sony Interactive Entertainment nem com a Bluepoint Games. /
> This project is not affiliated with Sony Interactive Entertainment or Bluepoint Games.

> **No se incluye ningún archivo del juego ni de Sony** (salvo los iconos de `glyphs/`, ver la sección
> en español). Necesitas tu propio dump del juego y, para el sonido, dos módulos de tu propia consola.

---

## Linux / CachyOS / AMD RDNA4 — v0.59.1-linux.3

**[Notas da release / Release notes](docs/releases/v0.59.1-linux.3.md)** ·
**[Download Linux distribution](https://github.com/abiason/ShadowOfTheColossus-PC-FIXED/releases/tag/v0.59.1-linux.3)**

Integração seletiva do AjncSystem v0.59.1 e de correções do shadPS4, preservando
as adaptações Linux/CachyOS e AMD RDNA4. **Distribuição nativa gerada no GitHub Actions**;
as instruções de uso do lançador Windows abaixo descrevem a base histórica.

Selective AjncSystem v0.59.1 and shadPS4 backports with the Linux/CachyOS and AMD
RDNA4 adaptations preserved. **Native distribution built in GitHub Actions.**
The Windows launcher instructions below describe the inherited project.

**Pacote publicado / Published package:** o tarball da v0.59.1-linux.3 foi
testado por dez minutos em PS4 Pro, 30 FPS e fullscreen: 119 amostras,
média 29,21 FPS, mínima 18,7 e máxima 30, sem falha fatal registrada.
Imagem, áudio e controles confirmados; instalação e hashes preservados. /
The published tarball passed a ten-minute PS4 Pro, 30 FPS fullscreen test:
119 samples, mean 29.21 FPS, minimum 18.7, maximum 30; no logged fatal fault.
Video, audio and controls confirmed; package files remained unchanged.
The following 30/60 FPS results refer to earlier local GUI builds.

- **Ambiente / Hardware:** CachyOS, Ryzen 7 5700X, Radeon RX 9060 XT 16 GB,
  32 GB RAM, Mesa RADV/Vulkan; CUSA08809.
- **Validação / Validation:** dois testes pela interface de pelo menos dez minutos, sem falha fatal
  ou perda do dispositivo Vulkan registrada; imagem, áudio e controles confirmados
  pelo usuário. / Two GUI runs of at least ten minutes without a logged fatal fault or Vulkan
  device loss; the user confirmed video, audio and controls.
- **30 FPS, sem patch / without patch:** média das amostras 29,77 FPS, mínima 23,9.
- **60 FPS experimental, com patch / patched:** média das amostras 52,27 FPS,
  mínima 28,8; não mantém 60 FPS constantes / does not sustain 60 FPS.
- **Correções / Fixes:** shaders e descritores, cópias de mips/camadas, associação
  stencil, memória sparse, sincronização CE/DE, liberação de corrotinas e offset
  de filas compute. O launcher Linux PS4 Pro usa 5376 MiB de memória direta.

As médias são de amostras periódicas, não percentis de frametime. O teste de
10 minutos não cobre todo o jogo. Persistem avisos do recompilador e artefatos
residuais; outras GPUs/distribuições e Windows não foram revalidados neste lote.
The measurements are periodic FPS samples, not frame-time percentiles; coverage
is limited and Windows was not retested for this batch.

**Build on Linux:** [dependências e build isolado / dependencies and isolated build](docs/sotc/README-Linux-CachyOS-RDNA4.md#integração-contínua-e-distribuição).

**Interface gráfica Linux / Linux GUI (experimental):**
`python3 launcher/sotc_launcher.py` — requer / requires Tk.
[Configuração e perfis / Setup and profiles](docs/sotc/README-Linux-CachyOS-RDNA4.md#interface-gráfica-linux-experimental).
Esta release inclui a interface e o empacotamento automatizado. Jogar/Parar foi validado em 30 e 60 FPS,
com imagem, áudio e controles confirmados pelo usuário. / This release includes
the launcher and automated packaging. Play/Stop was tested at 30 and 60 FPS; the user confirmed video,
audio and controls.

**Guia / Guide:** [Linux / CachyOS / AMD RDNA4](docs/sotc/README-Linux-CachyOS-RDNA4.md) ·
[Registro técnico / Integration report](docs/sotc/INTEGRACAO-SHADPS4.md)

Suporte Linux experimental. Dump do jogo e módulos de áudio devem ser fornecidos
pelo usuário; nenhum arquivo proprietário é distribuído.


**Build automatizado / Automated build:**
[Linux distribution](https://github.com/abiason/ShadowOfTheColossus-PC-FIXED/actions/workflows/linux-distribution.yml)
gera o tarball e `SHA256SUMS` em ambiente isolado; tags Linux publicam uma
pré-release após o build passar. / Builds the tarball and checksums in an
isolated environment; Linux tags publish a prerelease after successful checks.
O CI não possui o jogo: os números acima são dos testes locais anteriores,
não do artefato gerado pelo Actions. / CI has no game data; the measurements
above refer to previous local runs, not the Actions-built binary.

---

## Español

Port nativo de **Shadow of the Colossus** de PS4 (Bluepoint, 2018; CUSA08809, versión EU 1.01)
para **Windows 10/11**. El código x86-64 del propio juego se ejecuta directamente en la CPU del PC y
la GPU del PS4 se traduce a Vulkan. No es un emulador completo: es un cargador con las funciones de
sistema que el juego necesita, al estilo de [bloodborne_pc](https://github.com/Supermedo/bloodborne_pc).

La base heredada de xeodeo (**v0.57-fixed.1**) está centrada en **tarjetas AMD** y en rendimiento. Parte de la rama de
rendimiento de DUDUYG (PR #69 del proyecto original, con la PR #32 de Gabriell-os) y añade arreglos
propios y de otros forks. Notas completas: [docs/releases/v0.57-fixed.1.md](docs/releases/v0.57-fixed.1.md).

> **Aviso:** los iconos de botones Xbox/Nintendo de `glyphs/` están hechos a partir de las texturas de
> los iconos del juego. En la próxima versión se generarán en tu PC a partir de tu propio dump y se
> retirarán del repositorio.

### Novedades

| Versión | Mejoras y correcciones |
|---|---|
| **0.59.1-linux.3** | Distribución nativa Linux automatizada en GitHub Actions, hashes y registro del build; requiere bibliotecas compatibles del sistema. [Notas](docs/releases/v0.59.1-linux.3.md). |
| **0.59.1-linux.2** | Launcher gráfico Linux reutilizado del SotC: perfiles 30/60 FPS, archivos preparados, configuración XDG y botones Jugar/Parar validados. [Notas](docs/releases/v0.59.1-linux.2.md). |
| **0.59.1-linux.1** | Integración Linux/CachyOS/RDNA4 con mejoras selectivas de AjncSystem y shadPS4. Validación final a 30 y 60 FPS; 60 FPS experimental. Release de código fuente, sin binarios. [Notas](docs/releases/v0.59.1-linux.1.md). |
| **0.57-fixed.1** | **AMD RDNA3/RDNA4:** arreglado el bloque negro abajo a la izquierda ([#43](https://github.com/AjncSystem/ShadowOfTheColossus-PC/issues/43): faltaba una barrera entre el borrado de la ventana y la copia de la imagen). **Sombras sin rayas** en el suelo alrededor de Wander y Agro ([#27](https://github.com/AjncSystem/ShadowOfTheColossus-PC/issues/27)). **Texturas BC5/BC6H** creadas sin uso *storage* cuando el driver de AMD lo rechaza. **Rendimiento:** base de DUDUYG (+5% frente a la opt4) y PGO de Clang (+2,6%), medidos en una Radeon 780M. **Menú dentro del juego** (Insert o L2 + R3), **iconos Xbox/Nintendo** en los avisos del juego, **lanzador en español** y página de **Controles** con vibración y reasignación del mando. |
| **0.57** | **Tarjetas AMD:** corrección de los colores verdes/rosas en la niebla y en los personajes. **Opción nueva** en el lanzador para apagar el acceso directo a memoria: ~10% más FPS, agua lejana más plana. |
| **0.56** | **Agua del mundo abierto con olas:** los lagos y ríos bajo las cascadas ya no quedan lisos como un espejo (se ignoraba una instrucción de shader, `S_WQM_B64`). **El lago de arriba ondula y refleja hasta lejos.** Árboles lejanos sin "basura de colores". |
| **0.0.13** | **Sin cierres:** corregido el cierre en la apertura/menú de la 0.0.12. **Reflejos del lago** en casi toda la superficie, con ondulación. |
| **0.0.12** | **Texturas nítidas de vuelta, sin que el juego se cierre:** corregida la corrupción de memoria al cargar una partida y vuelto el streaming de texturas. **Agua:** salpicaduras, anillos y espuma al nadar; reflejos del cielo, del sol y de cada *probe*. |
| **0.0.11** | Corregida la hierba con textura de "basura de colores" de la 0.0.10. |

Detalles de cada versión en el [CHANGELOG](CHANGELOG.md).

### Problemas conocidos

- En el primer arranque tras actualizar se vuelven a compilar los shaders: la primera carga tarda y da
  tirones.
- En el campo abierto (5.000–6.500 comandos por fotograma) una gráfica integrada como la Radeon 780M
  sigue entre 20 y 26 FPS: el límite es el hilo de la CPU que traduce los comandos del juego.
- Con 8 GB de memoria de vídeo, el uso queda cerca del límite en zonas grandes.

### Descarga y uso

1. Descarga el zip de la página [Releases](../../releases) y descomprímelo en una carpeta.
2. Abre **`SotC.exe`**. La primera vez, el lanzador busca solo en los discos del PC:
   - la carpeta del juego (el dump CUSA08809, con `eboot.bin`, `sce_module` y `sce_sys`);
   - los módulos de sonido (`libSceNgs2.sprx` y `libSceUlt.sprx`) de un shadPS4 que ya tengas, en la
     carpeta `user/sys_modules`, y los copia a la carpeta de datos del port;
   - una partida del juego en shadPS4, que ofrece importar;
   - los DLC del juego, si los hay: la carpeta `addcont` de shadPS4, o una carpeta con una subcarpeta por
     DLC. También se puede elegir en **Juego y partidas > Carpeta de DLC**.
3. Revisa la página **Juego y partidas**. La **biblioteca de juegos** funciona como la de shadPS4.
4. Pulsa **JUGAR**.

Requisitos: Windows 10/11 de 64 bits y una tarjeta gráfica con **Vulkan 1.3** (NVIDIA, AMD o Intel con
el driver al día). No hace falta instalar Python.

#### Los archivos que necesitas

| Qué | De dónde | Para qué |
|---|---|---|
| Dump del juego CUSA08809 (mejor EU 1.01) | tu PS4, con GoldHEN | el juego |
| `libSceNgs2.sprx`, `libSceUlt.sprx` descifrados | tu PS4 (`/system/common/lib/`, FTP de GoldHEN), o el `user/sys_modules` de shadPS4 | el sonido (sin ellos el juego va mudo) |

Los modos de parche (60 FPS, filtro 16x) solo valen para la versión EU 1.01; en las demás el juego va
normalmente, a 30 FPS.

### El lanzador

- **Jugar:** comprueba la versión del juego, el sonido, las partidas y la tarjeta gráfica antes de
  abrir; opciones rápidas de salida, escalador, 60 FPS, filtro 16x y pantalla completa.
- **Juego y partidas:** biblioteca de juegos, búsqueda automática en el PC, importación de partidas de
  shadPS4.
- **Imagen y FPS:** salida de 720p a 4K (el juego renderiza a 1080p y FSR 1 + RCAS lo amplía), modo PS4
  Pro, efectos (viñeta, niebla, SSAO) y opciones de rendimiento.
- **Controles:** mando automático (DualShock 4, DualSense, Xbox); nombres e iconos de los botones
  PlayStation / Xbox / Nintendo; **iconos de botones dentro del juego**; **intensidad de la vibración**;
  reasignación de cada botón del juego a cualquier botón del mando; cámara con el ratón; cambio de
  teclas.
- **Avanzado:** idioma del lanzador (español, portugués, inglés), cvars del motor de Bluepoint,
  diagnóstico, acceso directo en el escritorio. El registro de cada sesión queda en `user/last_run.log`.

### El menú dentro del juego

Se abre con **Insert** en el teclado o **L2 + R3** en el mando. Muestra FPS, milisegundos por
fotograma, 1% low y comandos por fotograma, y cambia en vivo: mostrar FPS, estadísticas detalladas,
escalado FSR 1, nitidez (RCAS) y vibración. Mientras está abierto el juego no recibe la entrada. Se
maneja con la cruceta o las flechas (izquierda/derecha cambian el valor) y se cierra con Círculo, Esc o
el mismo atajo.

### Lo que se hizo

| Área | Resultado |
|---|---|
| Arranque | El juego arranca con el cargador de bbport: imports por NID, fibras, parches de CPU (SSE4a), imagen por debajo de 2 GiB (el juego guarda punteros de 31 bits). |
| Vídeo | Núcleo de vídeo del fork shadPS4 SotC dentro del port: logos, apertura, menús, campo abierto sin polígonos negros, sombras con iluminación correcta. |
| AMD | Sin bloque negro en RDNA3/RDNA4, sombras sin rayas, texturas BC5/BC6H sin uso *storage* no soportado. |
| Texturas | Streaming de texturas (el juego carga los mips más finos), sin corrupción de memoria. |
| Agua | Reflejos en espacio de pantalla, reflejos de entorno por *probe*, salpicaduras y anillos al nadar. |
| Partidas | Guardado, carga y borrado desde la lista de partidas en pantalla. |
| Sonido | Audio real con los módulos Ngs2/Ult del propio usuario. |
| Controles | Teclado y mando a la vez, cámara con el ratón, reasignación de teclas y del mando, vibración regulable, iconos Xbox/Nintendo dentro del juego. |
| Modos | 60 FPS, filtro anisotrópico 16x, modo PS4 Pro, salida hasta 4K. |
| Rendimiento | Hilo de preparación de dibujo y memos (DUDUYG), PGO de Clang, arreglos de CPU y memoria de otros forks. |

### Preguntas frecuentes

- **¿DirectX 11/12?** No. El núcleo de vídeo traduce la GPU del PS4 a Vulkan (shaders en SPIR-V). Toda
  tarjeta con DirectX 12 moderno tiene también Vulkan 1.3: basta con el driver al día.
- **¿AMD e Intel?** Esta versión se probó en una Radeon 780M. Dos optimizaciones solo se activan solas en
  NVIDIA: el envío periódico a la GPU y las lecturas anticipadas. En **Imagen y FPS > Envío de trabajo a
  la GPU**, elige **Activado** para usarlas en AMD o Intel (en la 780M dio +29% en las zonas pesadas). Si
  la pantalla se queda en negro, vuelve a **Automático**.
- **¿Por qué no viene el sonido?** Los dos `.sprx` son firmware de Sony; no se pueden distribuir. El
  lanzador encuentra y copia los tuyos automáticamente.
- **El juego se cerró solo.** Abre una *issue* con el archivo `user/last_run.log`.

### Compilar

MSYS2 CLANG64 (paquetes en `packaging/windows/README.md`) y `bash build.sh`. Para la versión con PGO:
compila con `-DBB_PGO=generate`, juega un rato con ese ejecutable (escribe `pgo/*.profraw` cada 30 s),
`llvm-profdata merge -o pgo/bbgpu.profdata pgo/*.profraw` y vuelve a compilar con `-DBB_PGO=use`.

---

## Português

Port nativo do **Shadow of the Colossus** de PS4 (Bluepoint, 2018; CUSA08809, versão EU 1.01)
para **Windows 10/11**. O código x86-64 do próprio jogo roda direto na CPU do PC e a GPU do PS4
é traduzida para Vulkan. Não é um emulador completo: é um carregador com as funções de sistema
de que o jogo precisa, no estilo do [bloodborne_pc](https://github.com/Supermedo/bloodborne_pc).

### Novidades

| Versão | Melhorias e correções |
|---|---|
| **0.59.1-linux.3** | Distribuição Linux nativa automatizada no GitHub Actions, hashes e registro do build; requer bibliotecas compatíveis do sistema. [Notas](docs/releases/v0.59.1-linux.3.md). |
| **0.59.1-linux.2** | Launcher gráfico Linux reaproveitado do SotC: perfis 30/60 FPS, imagens preparadas, configuração XDG e Jogar/Parar validados. [Notas](docs/releases/v0.59.1-linux.2.md). |
| **0.59.1-linux.1** | Integração Linux/CachyOS/RDNA4 com melhorias seletivas do AjncSystem e shadPS4. Validação final em 30 e 60 FPS; 60 FPS experimental. Release de código-fonte, sem binários. [Notas](docs/releases/v0.59.1-linux.1.md). |
| **0.57-fixed.1** | **AMD RDNA3/RDNA4:** corrigido o bloco preto no canto inferior esquerdo (issue #43: faltava uma barreira entre o clear da janela e a cópia da imagem). **Sombras sem listras** no chão perto do Wander e do Agro (issue #27). **Texturas BC5/BC6H** criadas sem uso *storage* quando o driver da AMD recusa. **Desempenho:** base do DUDUYG (+5% contra a opt4) e PGO do Clang (+2,6%), medidos numa Radeon 780M. **Menu no jogo** (Insert ou L2 + R3), **ícones Xbox/Nintendo** nos avisos do jogo, **lançador em espanhol** e página de **Controles** com vibração e remapeamento do controle. |
| **0.57** | **Placas AMD:** correção das cores verdes/rosas na névoa e nos personagens (as AMD passam a usar o caminho de 32 threads da NVIDIA; diagnóstico da issue #7, ainda não testado numa AMD). **Opção nova** no lançador para desligar o acesso direto à memória: ~10% mais FPS, água distante mais lisa. |
| **0.56** | **Água do mundo aberto com ondas:** lagos e rios abaixo das cascatas não ficam mais lisos como espelho (uma instrução de shader, `S_WQM_B64`, era ignorada). **Lago de cima ondula e reflete até longe** (acesso direto à memória ligado por padrão, como no Pink-shadPS4). Árvores distantes sem "lixo colorido". |
| **0.0.13** | **Sem quedas:** corrigida a queda na abertura/menu da 0.0.12 (o jogo pedia mais texturas do que cabe no pool). Testado ~40 min pelo mapa, com dois carregamentos de save. **Reflexos do lago** em quase toda a superfície, com ondulação (uma trava de laços dos shaders cortava os raios do reflexo). |
| **0.0.12** | **Texturas nítidas de volta, sem o jogo fechar:** a corrupção de memória que derrubava o jogo depois de carregar um save foi corrigida, e o streaming de texturas voltou (pedras e paredes bem mais nítidas). **Água:** respingos, anéis e espuma ao nadar; o lago reflete o céu e o brilho do sol; reflexos de ambiente com o *cubemap* certo de cada *probe* (correção do Pink-shadPS4). |
| **0.0.11** | Corrigida a grama com textura de "lixo colorido" da 0.0.10. |

Detalhes de cada versão no [CHANGELOG](CHANGELOG.md).

### Problemas conhecidos

- Na primeira abertura depois de atualizar, os shaders são compilados de novo: o primeiro
  carregamento demora e engasga.
- Placas **AMD**: a 0.57 traz a correção das cores verdes/rosas ([#7](../../issues/7)), ainda sem
  teste numa AMD. Se continuar, mande o seu `user/last_run.log` na issue.
- Com 8 GB de memória de vídeo, o uso fica perto do limite em áreas grandes.

### Download e uso

1. Baixe o `SotC-PC.zip` da página [Releases](../../releases) e descompacte numa pasta.
2. Abra o **`SotC.exe`**. Na primeira vez o lançador procura sozinho, nos discos do PC:
   - a pasta do jogo (o dump CUSA08809, com `eboot.bin`, `sce_module` e `sce_sys`);
   - os módulos de som (`libSceNgs2.sprx` e `libSceUlt.sprx`) de um shadPS4 que você já
     tenha, na pasta `user/sys_modules`, e copia para a pasta de dados do port;
   - um save do jogo no shadPS4, que ele oferece importar;
   - as DLCs do jogo, se houver: a pasta `addcont` do shadPS4, ou uma pasta com uma subpasta por DLC.
     Também dá para escolher em **Jogo e saves > Pasta de DLC**.
3. Confira a página **Jogo e saves**. A **biblioteca de jogos** funciona como a do shadPS4:
   adicione as pastas dos seus jogos e escolha o jogo na lista.
4. Clique em **JOGAR**.

Requisitos: Windows 10/11 64-bit, placa de vídeo com **Vulkan 1.3** (NVIDIA, AMD ou Intel
com driver recente). Não precisa instalar Python.

#### Os arquivos que você precisa ter

| O quê | De onde | Para quê |
|---|---|---|
| Dump do jogo CUSA08809 (EU 1.01 de preferência) | o seu PS4, pelo GoldHEN | o jogo |
| `libSceNgs2.sprx`, `libSceUlt.sprx` decriptados | o seu PS4 (`/system/common/lib/`, FTP do GoldHEN), ou o `user/sys_modules` do shadPS4 | som (sem eles o jogo roda mudo) |

Os modos de patch (60 FPS, filtro 16x) só valem para a versão EU 1.01; nas outras o jogo roda
normalmente, a 30 FPS.

### O lançador

- **Jogar:** confere a versão do jogo, o som, os saves e a placa de vídeo antes de abrir;
  opções rápidas de saída, upscaler, 60 FPS, filtro 16x e tela cheia.
- **Jogo e saves:** biblioteca de jogos, busca automática no PC, importação de saves do shadPS4.
- **Imagem e FPS:** saída 720p a 4K (o jogo renderiza em 1080p e o FSR 1 + RCAS amplia),
  modo PS4 Pro (o jogo oferece Cinematográfico/Desempenho no próprio menu), efeitos (vinheta,
  névoa, SSAO) e opções de desempenho.
- **Controles:** controle (DualShock 4, DualSense, Xbox) automático; câmera no mouse;
  **troca de teclas** clicando na ação e apertando a tecla nova.
- **Avançado:** cvars do motor Bluepoint, diagnóstico, atalho na área de trabalho (com o ícone
  do seu jogo). O registro de cada sessão fica em `user/last_run.log`.

### O que foi feito

| Área | Resultado |
|---|---|
| Boot | O jogo inicia com o carregador do bbport: imports por NID, fibras, patches de CPU (SSE4a), imagem abaixo de 2 GiB (o jogo guarda ponteiros em 31 bits). |
| Vídeo | Núcleo de vídeo do fork shadPS4 SotC dentro do port: logos, abertura, menus, campo aberto sem polígonos pretos, sombras com iluminação correta. |
| Texturas | Streaming de texturas (o jogo carrega os mips mais finos), sem corrupção de memória. |
| Água | Reflexos em espaço de tela, reflexos de ambiente por *probe*, respingos e anéis ao nadar. |
| Saves | Gravação, carregamento e exclusão pela lista de saves na tela. |
| Som | Áudio real com os módulos Ngs2/Ult do próprio usuário. |
| Controles | Teclado e controle juntos, câmera no mouse, troca de teclas no lançador. |
| Modos | 60 FPS (patch de illusion), filtro anisotrópico 16x, modo PS4 Pro, saída até 4K. |
| Desempenho | No demo da tela de título, em modo 60 FPS: média de **37–45 → ~67 FPS**, trecho mais pesado (ponte do cânion) **~17 → 29–34 FPS**. |

### Perguntas comuns

- **DirectX 11/12?** Não. O núcleo de vídeo traduz a GPU do PS4 para Vulkan (shaders em SPIR-V).
  Toda placa com DirectX 12 moderno também tem Vulkan 1.3: basta o driver atualizado.
- **AMD e Intel?** Quase todas as otimizações valem para qualquer placa. Duas só ligam
  sozinhas na NVIDIA: o envio periódico à GPU e as leituras antecipadas. Em **Imagem e FPS >
  Envio de trabalho à GPU**, escolha **Ligado** para usá-las numa AMD ou Intel. Se a tela ficar
  preta, volte para **Automático**.
- **Por que não vem o som pronto?** Os dois `.sprx` são firmware da Sony; distribuí-los não é
  permitido. O lançador acha e copia os seus automaticamente.
- **O jogo fechou sozinho.** Abra uma *issue* com o arquivo `user/last_run.log`.

---

## English

A native Windows port of the PS4 **Shadow of the Colossus** (Bluepoint, 2018; CUSA08809, EU 1.01)
for **Windows 10/11**. The game's own x86-64 code runs directly on the PC's CPU and the PS4 GPU
is translated to Vulkan. It is not a full emulator: it is a loader with the system functions the
game needs, in the style of [bloodborne_pc](https://github.com/Supermedo/bloodborne_pc).

### What's new

| Version | Improvements and fixes |
|---|---|
| **0.59.1-linux.3** | Automated native Linux distribution in GitHub Actions, checksums and build record; compatible host libraries required. [Notes](docs/releases/v0.59.1-linux.3.md). |
| **0.59.1-linux.2** | Shared SotC GUI adapted for Linux: 30/60 FPS profiles, prepared images, XDG settings and validated Play/Stop. [Notes](docs/releases/v0.59.1-linux.2.md). |
| **0.59.1-linux.1** | Selective AjncSystem/shadPS4 backports for Linux/CachyOS/RDNA4. Final 30/60 FPS validation; 60 FPS remains experimental. Source-only release, no binaries. [Notes](docs/releases/v0.59.1-linux.1.md). |
| **0.57-fixed.1** | **AMD RDNA3/RDNA4:** fixed the black block in the lower left (issue #43: a barrier was missing between the window clear and the image copy). **Shadows without stripes** on the ground around Wander and Agro (issue #27). **BC5/BC6H textures** created without storage usage when AMD's driver refuses it. **Performance:** DUDUYG base (+5% vs opt4) and Clang PGO (+2.6%), measured on a Radeon 780M. **In-game menu** (Insert or L2 + R3), **Xbox/Nintendo icons** in the game's prompts, **Spanish launcher** and a **Controls** page with vibration and gamepad remapping. |
| **0.57** | **AMD cards:** fix for the green/pink fog and characters (AMD now uses the NVIDIA 32-lane path; diagnosis from issue #7, not yet tested on an AMD card). **New launcher option** to turn off direct memory access: ~10% more FPS, flatter distant water. |
| **0.56** | **Open-world water with waves:** lakes and rivers below the waterfalls are no longer flat as a mirror (a shader instruction, `S_WQM_B64`, was ignored). **The upper lake ripples and reflects far away** (direct memory access on by default, as in Pink-shadPS4). Distant trees without "colored garbage". |
| **0.0.13** | **No more crashes:** fixed the 0.0.12 crash in the intro/menu (the game asked for more textures than its pool holds). Tested ~40 min across the map with two save loads. **Lake reflections** over almost the whole surface, with ripples (a shader loop guard cut the reflection rays short). |
| **0.0.12** | **Sharp textures back, without crashes:** fixed the memory corruption that closed the game after loading a save, and texture streaming is back (much sharper rocks and walls). **Water:** splashes, rings and foam while swimming; the lake reflects the sky and the sun's glint; environment reflections use each probe's correct cubemap (fix from Pink-shadPS4). |
| **0.0.11** | Fixed the "colored garbage" grass texture of 0.0.10. |

Full details in the [CHANGELOG](CHANGELOG.md) (in Portuguese).

### Known issues

- The first start after updating rebuilds the shaders: the first load is slow and stutters.
- **AMD** GPUs: 0.57 has the fix for the green/pink tint ([#7](../../issues/7)), not yet tested
  on an AMD card. If it persists, attach your `user/last_run.log` to the issue.
- With 8 GB of video memory, usage gets close to the limit in large areas.

### Download and use

1. Download `SotC-PC.zip` from [Releases](../../releases) and unzip it into a folder.
2. Run **`SotC.exe`**. On first start the launcher searches the PC's drives for:
   - the game folder (the CUSA08809 dump with `eboot.bin`, `sce_module` and `sce_sys`);
   - the sound modules (`libSceNgs2.sprx` and `libSceUlt.sprx`) of an installed shadPS4
     (`user/sys_modules`), which it copies to the port's data folder;
   - a shadPS4 save of the game, which it offers to import;
   - the game's DLCs, if any (shadPS4's `addcont` folder, or a folder with one subfolder per DLC).
3. Check the **Game and saves** page. The **game library** works like shadPS4's.
4. Click **PLAY**.

Requirements: Windows 10/11 64-bit and a **Vulkan 1.3** GPU (NVIDIA, AMD or Intel with a recent
driver). No Python install needed.

| What | Where from | What for |
|---|---|---|
| CUSA08809 game dump (EU 1.01 preferred) | your PS4, through GoldHEN | the game |
| decrypted `libSceNgs2.sprx`, `libSceUlt.sprx` | your PS4 (`/system/common/lib/`, GoldHEN FTP), or shadPS4's `user/sys_modules` | sound (silent without them) |

The patch modes (60 FPS, 16x filtering) only apply to EU 1.01; other versions run at 30 FPS.

### Launcher features

Game library and automatic search, shadPS4 save import, 720p–4K output (the game renders at
1080p, upscaled with FSR 1 + RCAS), PS4 Pro mode, 60 FPS and 16x AF modes, controller support
(DualShock 4, DualSense, Xbox) with mouse camera, key remapping, Bluepoint engine cvars, desktop
shortcut and a session log in `user/last_run.log`.

In 60 FPS mode the title-screen attract demo averages ~67 FPS on an RTX 2060 SUPER, with
29–34 FPS in its heaviest section. Vulkan only (no DirectX). AMD and Intel can enable the
NVIDIA-only submission options under **Image and FPS > GPU work submission**.

**Why no sound files?** The two `.sprx` files are Sony firmware and may not be redistributed;
the launcher finds and copies yours automatically. **The game closed by itself?** Open an issue
with `user/last_run.log`.

---

## Compilar / Building

Windows com / with [MSYS2](https://www.msys2.org/) (CLANG64). Pacotes / packages:
[packaging/windows/README.md](packaging/windows/README.md). Para congelar o `SotC.exe` / to
freeze `SotC.exe`: um Python do Windows com PyInstaller e Pillow / a Windows Python with
PyInstaller and Pillow (`WINPYTHON`).

```
bash build.sh                              # out/bb-probe.exe
bash packaging/windows/package_sotc.sh     # dist/SotC-PC.zip
```

O empacotamento recusa qualquer `.sprx`/`.prx` / packaging refuses any `.sprx`/`.prx`: Sony
firmware never goes into the package. Ferramentas de teste / test tools: `tools/`. Variáveis de
diagnóstico / diagnostic variables: [docs/sotc/README-SotC.md](docs/sotc/README-SotC.md).

## Créditos / Credits

- [bloodborne_pc](https://github.com/Supermedo/bloodborne_pc) (Supermedo, deadinside28 and
  forks): carregador, runtime nativo e lançador / loader, native runtime and launcher. README
  original: [docs/bbport](docs/bbport/README.md).
- [shadPS4](https://github.com/shadps4-emu/shadPS4) e o fork / and the shadPS4 SotC fork:
  núcleo de vídeo Vulkan / Vulkan video core.
- [Pink-shadPS4](https://github.com/luizgustavs/Pink-shadPS4) (luizgustavs): cvars de culling /
  culling cvars, BPE heap guard, envio periódico / periodic submission, gravador de comandos em
  thread própria / command recording thread, correções de shader / shader fixes (fetch-shader
  constants, `V_ALIGNBIT`, `V_CVT_PK_U8_F32`), tabelas de texturas indexadas / dynamic T# tables
  (`dynamic_tsharp_array_size`), a abordagem das estatísticas de LOD / the LOD statistics
  approach e o acesso direto à memória para o SotC / and direct memory access for SotC.
- Patch de 60 FPS / 60 FPS patch: illusion (GoldHEN cheats).

Licença / License: **GPL-2.0-or-later** ([LICENSE](LICENSE)).
