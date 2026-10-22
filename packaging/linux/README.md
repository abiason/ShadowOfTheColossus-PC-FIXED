# Pacote nativo SotC para Linux/CachyOS

Este empacotador produz um `.tar.gz` com o launcher Tkinter, runner,
executáveis locais, scripts de preparação e licenças. Não é AppImage nem
pacote universal: depende das bibliotecas do sistema compatíveis com o build.
Não usa os scripts antigos de empacotamento do Bloodborne.

## Gerar

Compile primeiro o projeto e instale `patchelf` na máquina de empacotamento.
No CachyOS: `sudo pacman -S --needed patchelf`.

```bash
python3 packaging/linux/package_sotc.py
```

O arquivo recebe nome único em `dist/`. `--output DIRETORIO` muda esse local.
A geração não altera os executáveis originais: copia para um estágio temporário
e ajusta apenas o RUNPATH de `bin/bb-probe` para `$ORIGIN/gpu`.
O layout `bin/gpu/libbbgpu.so` permite localizar a biblioteca extraída.

O FSR modificado é recusado por padrão. Para uma **prévia privada local**:

```bash
python3 packaging/linux/package_sotc.py --allow-dirty-fsr --output out/pacote-local
```

Esse modo marca `private_preview_only` no manifesto e não publica nem envia
arquivos. Preserva o submódulo e não copia seus fontes modificados, mas a
biblioteca GPU existente pode conter os efeitos dessas alterações.
Mesmo com Git limpo, hashes e commit não provam de qual fonte ou compilador
os executáveis locais foram gerados; não há atestado de build reproduzível.
Um pacote público requer preparação e validação do build correspondente.

## Usar

Extraia o tarball em uma pasta e execute `./SotC.sh`. O sistema precisa de
Python 3/Tkinter e das dependências nativas do build. O ambiente atual exige
GLIBC 2.43, GLIBCXX 3.4.36 e os SONAMEs recentes do FFmpeg (avformat/avcodec63,
avutil61, swscale10 e swresample7), além de SDL3, Vulkan, fmt, Zydis/Zycore,
xxhash e suas dependências. A compatibilidade deve ser verificada no sistema
de destino. Não são incluídos glibc, drivers Vulkan ou bibliotecas do host.
Pillow é opcional para redimensionar as imagens do próprio dump.

O wrapper define `SOTC_DATA_DIR` por padrão como
`${XDG_DATA_HOME:-$HOME/.local/share}/sotc-pc`. Nesse diretório ficam:

- `sotc.ini`: controles e configuração do runner;
- `out/launcher-linux`: modos e cmdline, com imagens preparadas em `prepared/`;
- `user/`: dados padrão, saves e logs, quando nenhuma pasta foi escolhida.

É possível definir `SOTC_DATA_DIR` para outro local. O launcher mantém suas
preferências em `${XDG_CONFIG_HOME:-$HOME/.config}/sotc-launcher/settings.json`.
Uma pasta de usuário escolhida previamente continua sendo respeitada.
Atalhos `.desktop` criados pela interface preservam `SOTC_DATA_DIR`.
A pasta do programa pode permanecer somente leitura.

Forneça seu dump e módulos de áudio ou selecione suas imagens já preparadas.
O pacote não contém jogo, firmware `.prx/.sprx`, saves, imagens vinculadas,
configurações pessoais, caches, logs nem modelos opcionais externos de FSR.
Os ícones de botões substituídos a partir de texturas do jogo também não são
coletados. Fonte de overlay e shaders host já estão incorporados ao binário.

`MANIFEST.json` registra commit, estado local, hashes dos executáveis de entrada
e hashes dos arquivos após preparação. As licenças ficam em `licenses/`.
O manifesto é de identificação e integridade; não é assinatura digital.

## Validação

```bash
python3 -m unittest discover -s tests -p 'test_sotc_linux_*.py'
```

Os testes verificam whitelist/exclusões, arquivos simbólicos recusados, ELF
x86_64, modos, hashes, preservação das imagens manuais e escrita dos dados
fora da instalação. O teste real do tarball relocacionado foi autorizado e concluído conforme
o registro abaixo. Novos testes controlados continuam exigindo confirmação.

Verificação local: 28 testes passaram; tarball privado gerado e extraído em
um caminho com espaços, hashes conferidos e libbbgpu resolvida no próprio
pacote, com RUNPATH apenas $ORIGIN/gpu. A interface abriu as seis páginas e
persistiu controles/preferências em dados externos com instalação somente
leitura. Nenhum jogo foi iniciado nessa verificação.

Teste real da prévia privada: 600 segundos a 30 FPS pelo wrapper SotC.sh,
instalação somente leitura em caminho com espaços, dados e preferências em
diretórios externos, imagem vinculada/content externos e sem perfil CPU
opcional. Neo/fullscreen, 5376 MiB, FSR1, filtro16x e vblank emulado60.
Sem falha fatal ou perda do dispositivo Vulkan registrada; Parar encerrou
o grupo por SIGTERM (-15), Jogar foi habilitado novamente. O usuário confirmou
imagem, áudio e controles normais e sincronizados. Foram 119 amostras até
597 segundos; média 29,85 FPS, mínima 27,4 e máxima 30,0. São amostras
periódicas, não percentis de frametime. Hashes do pacote permaneceram iguais
e não surgiram arquivos inesperados na instalação. Logs locais preservados
em out/validacao-pacote-linux/. Não é validação de um build limpo nem de
outros sistemas e ABIs; a prévia com FSR modificado não foi publicada.


## Build automatizado no GitHub

O workflow [Linux distribution](../../.github/workflows/linux-distribution.yml)
faz checkout limpo com submódulos, instala dependências em container CachyOS
x86-64 fixado por digest e baixa VMA por commit e SHA256. Compila com
`BB_BUILD_JOBS=2 BB_PGO=off BB_LTO=OFF`, executa testes e gera o tarball e
`SHA256SUMS`. Pushes na main, PRs relevantes e Run workflow geram artefatos.
Tags `v*-linux.*` também publicam uma pré-release após o job de build passar.

O empacotador aceita `--allow-versioned-fsr-patches --build-record
out/build-provenance.json` somente quando o diff completo do FSR corresponde
exatamente aos patches do HEAD, sem mudanças adicionais, staged ou arquivos
extras. O comparador usa índice e object store temporários, sem alterar o
FSR original. Commits e hashes do registro devem coincidir com os fontes e
executáveis de entrada. O modo de prévia privada continua separado.

`BUILD-PROVENANCE.json` registra ferramentas, pacotes, flags, commits,
hashes e execução do Actions; não é atestação criptográfica. Os repositórios
da distribuição são rolling: imagem fixada e versões registradas não
significam build bit a bit reproduzível. O CI não possui dump nem módulos
proprietários e não executa o jogo. A validação humana anterior foi feita
no ambiente local descrito acima, não no runner GitHub.

## AppImage e Latest — linux.4

O workflow também gera um AppImage x86_64 a partir do tarball verificado.
Inclui Python/stdlib, Tkinter/Pillow, Tcl/Tk e dependências nativas selecionadas,
com licenças e lista de pacotes. Exclui glibc/carregador ELF e a pilha de
Vulkan/drivers gráficos, que vêm do host. Alvo: CachyOS com glibc 2.43 e ABI
compatível; o formato não implica compatibilidade com distribuições antigas.

```bash
python3 packaging/linux/appimage.py dist/ARQUIVO.tar.gz --output dist --work out/appimage-build
xvfb-run -a python3 packaging/linux/verify_appimage.py dist --gui
```

O diretório de trabalho deve ser novo. Além dos requisitos anteriores, instale
`licenses`, `desktop-file-utils`, `xorg-server-xvfb`, `xorg-xauth` e uma fonte
como `ttf-dejavu`. Ferramenta/runtime AppImage são baixados de versões oficiais
fixadas, com SHA256 em `appimage-tools.json`; a criação não depende de FUSE.

A verificação executa o AppImage real com `--appimage-extract-and-run`, confere
seu manifesto, importa o runtime incluído e abre as páginas da GUI em Xvfb.
Dados/configurações vão para diretórios temporários externos. Não inicia o
jogo, nem testa gameplay ou áudio. `out/appimage-verification.json` registra
esse escopo. `SHA256SUMS` cobre tarball, AppImage e `APPIMAGE-BUNDLE.json`.

Para usar, confira os hashes e execute:

```bash
chmod +x SotC-PC-*-x86_64.AppImage
./SotC-PC-*-x86_64.AppImage
# Alternativa sem FUSE:
./SotC-PC-*-x86_64.AppImage --appimage-extract-and-run
```

Os dados continuam em XDG, com override `SOTC_DATA_DIR`. O atalho criado pela
GUI aponta para o arquivo AppImage persistente; movê-lo exige recriar o atalho.
A release em tag é publicada como Latest após as verificações. Linux e 60 FPS
continuam experimentais; Latest é a seleção de distribuição no GitHub.
