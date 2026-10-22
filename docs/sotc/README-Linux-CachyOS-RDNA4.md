# Shadow of the Colossus — Linux / CachyOS / AMD RDNA4

Documentação experimental da adaptação Linux desenvolvida por abiason, baseada nos projetos de AjncSystem e xeodeo.

## Release v0.59.1-linux.1

[Notas completas](../releases/v0.59.1-linux.1.md) ·
[Release no GitHub](https://github.com/abiason/ShadowOfTheColossus-PC-FIXED/releases/tag/v0.59.1-linux.1)

Pré-release de código-fonte, sem binários, com a integração seletiva AjncSystem
v0.59.1 e os backports shadPS4 validados neste fork. Nos testes finais de dez
minutos, sem falha fatal registrada, a média das amostras foi 29,78 FPS no
perfil 30 (mínima 24,5) e 49,96 FPS no perfil 60 experimental (mínima 28,5).
O usuário confirmou imagem, áudio e controles normais. Não garante desempenho
constante ou cobertura de todo o jogo. O ambiente testado preservava alterações
locais do FSR excluídas da release; compilação limpa da tag ainda não revalidada.

## Ambiente testado
- Sistema operacional: CachyOS Linux
- Processador: AMD Ryzen 7 5700X
- Placa de vídeo: AMD Radeon RX 9060 XT 16 GB (RDNA4)
- Driver gráfico: Mesa RADV / Vulkan
- Memória RAM: 32 GB DDR4
- Jogo: Shadow of the Colossus (PS4, CUSA08809)

## Compilação
Dependências: GCC, CMake, Ninja, pkg-config, Vulkan, SDL3 e submódulos do projeto.

```bash
env BB_PGO=off BB_LTO=OFF bash build.sh
```

O executável será gerado em `out/bb-probe`.

## Interface gráfica Linux (em desenvolvimento)

A interface Tkinter do SotC é compartilhada com o Windows. Para abri-la:

```bash
python3 launcher/sotc_launcher.py
```

No CachyOS, a biblioteca Tk é necessária (`sudo pacman -S --needed tk`).
Pillow é opcional para redimensionar as imagens do próprio dump. O launcher
não compila o projeto nem inicia o jogo ao abrir a janela.

- **Jogo e saves:** selecione o dump CUSA08809 e os módulos de áudio do seu
  console. Para reutilizar a preparação já existente, selecione também
  `boot-linked.bin` e `content.bin`; o perfil `sotc-cpu.bin` é opcional.
  A imagem vinculada deve conter os módulos de áudio. Os dois primeiros
  campos precisam ser preenchidos juntos. Saves não são importados
  automaticamente na configuração inicial Linux; há importação manual.
- **Imagem e FPS:** sem marcar 60 FPS, usa limite de 30; marcado, aplica o
  patch experimental de 60 FPS quando a versão do dump é compatível.
  Ambos os perfis Linux usam vblank emulado de 60 Hz. PS4 Pro habilita as
  opções do jogo, mas o modo Desempenho deve ser selecionado dentro dele.
- **Controles e Avançado:** mantém as opções de teclado, mouse, gamepad,
  vibração, idioma, variáveis extras, atalhos e logs da interface existente.
  No Linux, valores extras com espaços podem ser escritos como
  `SOTC_CACHE_DIR="/caminho/cache com espaços"`. Overrides são intencionais e
  podem mudar o perfil validado.
- **Jogar / Parar:** o launcher inicia o runner nativo e interrompe seu grupo
  de processos. O registro aparece na interface e em `user/last_run.log`
  (ou na pasta de dados selecionada). Nenhum comando é montado por shell.

Os padrões Linux são PS4 Pro, fullscreen, DMA desligado, memória direta de
5376 MiB, EOP defer desligado e readback assíncrono desligado. O filtro 16x
começa desmarcado. As preferências ficam em
`${XDG_CONFIG_HOME:-~/.config}/sotc-launcher/settings.json`, separadas das
configurações Windows. Um arquivo legado `~/sotc-launcher/settings.json`
é lido como fallback e salvo no novo local quando houver gravação.

A preparação automática Linux fica em `out/launcher-linux/prepared`; patches
e cmdline em `out/launcher-linux`. Não sobrescreve as imagens manuais em
`out/boot-linked.bin` ou os arquivos externos selecionados. Com arquivos
preparados, não executa a preparação nem refaz o vínculo dos módulos.
O comando de terminal e o script de execução já testados continuam disponíveis.

Validação desta adaptação: 19 testes automatizados, abertura e navegação nas
seis páginas com configuração temporária, persistência e geração de modes
com o dump real equivalente aos arquivos já testados. O teste do jogo iniciado pela interface em 30 FPS ultrapassou dez minutos,
sem falha fatal ou perda do dispositivo Vulkan registrada. Parar encerrou
o grupo por SIGTERM (saída -15), e Jogar foi habilitado novamente. A primeira
tentativa revelou o watchdog padrão de dez segundos do loader; o runner
agora passa --timeout 0 por padrão, com override explícito ainda permitido.
A interface não foi revalidada visualmente em Windows. Os testes do backend verificam a preservação dos
padrões de timing Windows.

## Correções de compatibilidade Linux
- Reserva da imagem do jogo abaixo de 2 GiB com mmap e MAP_FIXED_NOREPLACE.
- Ajustes de compilação GCC e definição de _GNU_SOURCE.
- Inclusão dos cabeçalhos Xbyak no CMake.
- Substituição de MAX_PATH no código de gerenciamento de páginas.
- Correção do tipo de retorno de uma lambda no rasterizador Vulkan.
- Restrição da chamada install_heap_hook() ao Windows.
- Símbolos provisórios de heap no Linux, sem implementação equivalente ao Windows.

## Resultados observados
- Inicialização e execução bem-sucedidas no CachyOS.
- Áudio funcional utilizando módulos compatíveis do próprio usuário.
- Teste contínuo de aproximadamente 37 minutos e 41 segundos.
- 30 FPS estáveis observados com MangoHud no teste inicial; os testes posteriores abaixo
  encontraram quedas em trechos mais longos.
- Redução de determinados artefatos de sombras em relação à versão anterior.

## Limitações conhecidas
- Artefatos gráficos residuais, especialmente nas sombras.
- Avisos Vulkan recorrentes e erros registrados pelo recompilador de shaders.
- O limite de 60 FPS não garante 60 FPS constantes; houve quedas abaixo de 30 FPS nos testes posteriores.
- Mecanismo de heap hook do Windows ainda não implementado no Linux.
- Compatibilidade com outras GPUs e distribuições ainda não validada.

## Créditos
- AjncSystem: projeto original ShadowOfTheColossus-PC.
- xeodeo: fork ShadowOfTheColossus-PC-FIXED.
- Supermedo/bloodborne_pc: base do carregador e runtime.
- shadPS4 e colaboradores: componentes gráficos Vulkan.
- abiason: adaptações de compatibilidade e testes Linux/CachyOS com AMD RDNA4.

Esta adaptação é experimental e não representa suporte oficial dos projetos originais.

## Execução experimental no Linux

A execução requer uma imagem vinculada do jogo, o diretório CUSA08809 e um perfil de conteúdo previamente preparado.

Exemplo com caminhos genéricos:

```bash
env SOTC_EOP_DEFER=0 ./out/bb-probe /caminho/para/boot-linked.bin --app0 /caminho/para/CUSA08809 --content-profile /caminho/para/content.bin --timeout 0
```

O comando pressupõe que a preparação e a vinculação da imagem já foram realizadas. Essas etapas ainda precisam de documentação reproduzível para Linux.

### Configuração testada: PS4 Pro / Desempenho

Na `main` em `46834bf`, a melhor configuração observada foi PS4 Pro com o modo
**Desempenho do próprio jogo**, limite de apresentação de 60 FPS e espera EOP
adicional desligada. Para executá-la com uma imagem já preparada:

```bash
bash tools/sotc_linux_pro.sh \
  /caminho/para/boot-linked.bin \
  /caminho/para/CUSA08809 \
  /caminho/para/content.bin
```

O script aplica somente ao processo iniciado:

```text
SOTC_NEO=1
BB_DMEM_MB=5376
BB_FPS_LIMIT=60
BB_VBLANK_HZ=60
SOTC_EOP_DEFER=0
BB_DIRECT_MEMORY_ACCESS=0
SOTC_RB_ASYNC=0
SOTC_FPS=1
```

Selecione **Opções → Apresentação → Modo Grafismo → Desempenho** dentro do jogo.
`SOTC_NEO=1` habilita as opções de PS4 Pro, mas não escolhe o modo Desempenho.
Esse ajuste também não é o preset Performance de um upscaler.
O limite do host permanece separado da frequência de vblank, mantida em 60 Hz.

O script não prepara imagens, não compila nem atualiza submódulos. Usa `user/`
no repositório por padrão; `SOTC_USER_DIR` permite escolher outro diretório.
O caminho do jogo e os dois arquivos são informados explicitamente, sem incluir
arquivos proprietários ou caminhos pessoais no script.

Por padrão a execução não tem timeout. Para testar por 10 minutos e guardar o log:

```bash
bash tools/sotc_linux_pro.sh \
  /caminho/para/boot-linked.bin \
  /caminho/para/CUSA08809 \
  /caminho/para/content.bin 600 > out/teste-pro-desempenho.log 2>&1
```

Acrescente `--dry-run` antes dos caminhos para conferir o comando sem abrir o jogo.
O script fixa os parâmetros acima, exceto `BB_DMEM_MB`, que pode ser sobrescrito
no ambiente; as demais variáveis e configurações existentes
continuam sendo herdadas. Não altera os padrões globais do projeto.

O orçamento de memória direta de 5376 MiB acompanha o modo PS4 Pro: o jogo o
reconheceu como Neo com zero de memória de depuração. Em um teste controlado
de demonstração sem interação, 5056 MiB apresentou falha em `0x1a371` após
cerca de 116 segundos, com bitmap sem bits ativos; 5376 MiB completou dez
minutos e as duas transições de partida, sem falha fatal registrada. O teste
usou fullscreen, patch experimental fps60 e diagnóstico adicional. Esse
resultado favorece o orçamento maior, mas não demonstra ausência de vazamentos
nem resolução definitiva da falha intermitente. O padrão genérico/base PS4
do runtime continua em 5056 MiB. Exemplo de override para comparação:

```bash
BB_DMEM_MB=5056 bash tools/sotc_linux_pro.sh --dry-run \
  /caminho/para/boot-linked.bin /caminho/para/CUSA08809 /caminho/para/content.bin
```

#### Comparativo da espera EOP

Dois testes de 10 minutos com PS4 Pro e `BB_FPS_LIMIT=60` registraram:

| Métrica | `SOTC_EOP_DEFER=1` | `SOTC_EOP_DEFER=0` |
| --- | --- | --- |
| Média das 119 amostras periódicas | 34,8 FPS | 49,3 FPS |
| Mediana das amostras | 33,4 FPS | 52,1 FPS |
| Faixa registrada | 17,0–60,0 FPS | 21,2–60,0 FPS |
| Amostras abaixo de 30 FPS | 38 | 11 |
| Uso máximo de VRAM registrado | 8.347 MB | 7.223 MB |

Ambos terminaram pelo timeout programado, sem registros fatais ou de perda do
dispositivo. O PipeWire foi inicializado. O usuário confirmou o modo Desempenho
no primeiro teste e imagem e áudio corretos no teste com EOP desligado.
A seleção do modo dentro do jogo não é identificada por esses logs.

`SOTC_EOP_DEFER=1` adia a sinalização EOP até a GPU terminar o trabalho enviado,
acrescentando uma espera. O código já usa `0` quando a variável não é informada.
O exemplo antigo desta documentação fixava `1`; o resultado acima motivou sua correção.
Desligar essa espera não desliga toda a sincronização da GPU.

As sessões não seguiram uma rota controlada idêntica: os números indicam uma
melhora observada, não um ganho causal exato nem garantia de 60 FPS constantes.
Os logs locais estão em `out/validacao-main-pro-fpslimit60.log` e
`out/validacao-main-pro-fpslimit60-eop0.log`; o resumo está em
`out/comparativo-pro-eop.json`. Esses artefatos não são versionados.

#### Validação de 30 minutos com o script

Uma sessão posterior executou `tools/sotc_linux_pro.sh` por 1.800 segundos com
PS4 Pro, modo Desempenho, limite de 60 FPS e `SOTC_EOP_DEFER=0`:

| Métrica | Resultado |
| --- | --- |
| Amostras periódicas | 358, até 1.794 segundos |
| Média das amostras | 51,8 FPS |
| Mediana das amostras | 56,3 FPS |
| Faixa registrada | 20,4–60,0 FPS |
| Amostras abaixo de 30 FPS | 26 |
| Amostras abaixo de 20 FPS | 0 |
| Uso máximo de VRAM registrado | 7.035 MB |

A sessão terminou pelo timeout programado, sem registros fatais, perda do
dispositivo, esgotamento de memória ou avisos `SanitizeCopyLayers`. O PipeWire
foi inicializado. Após ser consultado sobre imagem, áudio, combate e
salvamento/carregamento, o usuário confirmou que tudo estava correto.
Os aspectos visuais, sonoros e de jogabilidade são confirmação do usuário;
as estatísticas acima são provenientes do log.

Essa é a configuração recomendada para continuar os testes no ambiente informado.
O resultado não garante 60 FPS constantes nem compatibilidade fora desse ambiente.
Os artefatos locais são `out/validacao-pro-desempenho-30min.log` e
`out/validacao-pro-desempenho-30min-resumo.json`, não versionados.

#### Comparativo controlado no Santuário: culling de índices

O launcher já oferece uma opção que passa `doIndexBufferCulling=0` e
`doSunShadowIndexBufferCulling=0` ao motor do jogo. O script Linux original não
passava esse arquivo de parâmetros. As opções foram testadas separadamente,
mantendo PS4 Pro/Desempenho, EOP desligado e limite de 60 FPS.

O usuário posicionou personagem e câmera no mesmo enquadramento do Santuário.
Cada repetição aguardou 60 segundos de aquecimento após sua confirmação e mediu
os 120 seguintes, usando `SOTC_FRAME_TIMES` e sem `SOTC_CMD_STATS`:

| Métrica | Padrão | Culling de índices desligado |
| --- | --- | --- |
| FPS médio pelos intervalos de apresentação | 20,72 | 25,19 |
| 1% low | 18,12 FPS | 21,46 FPS |
| Frametime mediano | 48,1 ms | 39,8 ms |
| Percentil 99 do frametime | 53,2 ms | 45,0 ms |

O ganho observado de FPS foi de 21,6% nesse enquadramento, sem registros fatais
ou avisos `SanitizeCopyLayers` em ambas as execuções. Não garante 30 FPS nessa
cena nem o mesmo ganho em outras cenas. Em uma sessão posterior iniciada pela
opção `--sotc-cmdline` do script, o usuário confirmou imagem, sombras, objetos
e áudio corretos durante a jogabilidade com essas opções.

Essa sessão completou os 10 minutos pelo timeout programado, sem registros fatais,
perda do dispositivo, esgotamento de memória ou avisos `SanitizeCopyLayers`.
Foram registradas 119 amostras periódicas, com mediana de 25,3 FPS, faixa de
24,8–60,0 FPS e uso máximo de VRAM de 5.535 MB. A média dessas amostras foi
30,14 FPS, incluindo os trechos iniciais mais rápidos; ela não substitui o
comparativo controlado acima. O patamar final ficou próximo de 25 FPS.
O log local é `out/validacao-script-culling-10min.log` e seu resumo é
`out/validacao-script-culling-10min-resumo.json`, não versionados.
Isso valida a passagem dos parâmetros pelo script nessa sessão, sem garantir
ausência de problemas em todas as cenas ou em outros equipamentos.

Uma coleta anterior com contadores detalhados também ficou próxima de 21 FPS.
Na primeira comparação sem contadores, a carga variou nos primeiros 50 segundos;
a média daquela janela não foi usada para atribuir ganho à instrumentação.
Os contadores `work` são calculados por diferença de tempos, não constituindo
uma medição isolada de uso de CPU.

Os artefatos locais das repetições são `out/santuario-repeticao-padrao/` e
`out/santuario-repeticao-culling-off/`. Os CSVs, marcadores de janela e resumos
não são versionados. `tools/sotc_frame_summary.py` permite recalcular as métricas.

Para reproduzir a opção de culling sem alterar os padrões do script, gere um
arquivo de parâmetros separado a partir do seu próprio eboot EU 1.01:

```bash
mkdir -p out/culling-off
python3 scripts/sotc_modes.py /caminho/para/CUSA08809 \
  --out out/culling-off \
  --cvars 'doIndexBufferCulling=0 doSunShadowIndexBufferCulling=0'

bash tools/sotc_linux_pro.sh --sotc-cmdline out/culling-off/cmdline.bin \
  /caminho/para/boot-linked.bin \
  /caminho/para/CUSA08809 \
  /caminho/para/content.bin
```

O gerador verifica a versão do eboot; se não for compatível, não cria o arquivo
de parâmetros. O loader também verifica as instruções antes de aplicar o ajuste
somente à imagem em memória. Nenhum arquivo do jogo é sobrescrito. O arquivo
`patches.bin` gerado junto não é usado nesse comando; nenhum patch `fps60` é
solicitado. Para voltar à configuração anterior, basta omitir `--sotc-cmdline`.
Não basta exportar `SOTC_CVARS` ao executar `bb-probe` diretamente: o parâmetro
precisa ser gerado e passado ao loader, como acima.

### Áudio

O áudio foi testado com os módulos libSceNgs2.sprx e libSceUlt.sprx, obtidos legitimamente do firmware do próprio usuário.

### Arquivos proprietários

Este repositório não distribui arquivos do jogo, imagens vinculadas, dumps de firmware ou módulos proprietários da Sony.

### Monitoramento

O MangoHud foi utilizado para observar FPS e frametime. Os resultados descritos neste documento correspondem ao ambiente de teste informado acima.

O teste de 30 FPS pela GUI usou fullscreen, Neo, 5376 MiB, FSR1 e filtro 16x
ativado na interface. Foram 124 amostras até 622 segundos, com média
29,77 FPS e mínima 23,9 FPS. São amostras periódicas, não métricas de
frametime. Confirmação humana de imagem/áudio/controles deste teste e teste
do perfil de 60 FPS pela interface ainda pendentes. Logs preservados em
out/validacao-launcher-linux/.
