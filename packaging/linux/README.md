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
fora da instalação. O teste real de jogo a partir do tarball relocacionado
permanece separado e depende da autorização de teste controlado.
