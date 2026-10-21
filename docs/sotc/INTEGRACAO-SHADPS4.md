# Integração seletiva do shadPS4

Referência consultada: `shadps4/main` em `b61f6c57`, em 2026-10-20.
Base declarada do código incorporado: `b4e7ae776071ceb1dd35004577a8719481e1d258`.

## Correções aplicadas

| Commit upstream | Alteração |
| --- | --- |
| `524be7c1` | Exclui GetUserData da simplificação de Phi. |
| `603cff43` | Estabiliza a ordem de deduplicação de Phi. |
| `6752d8b1` | Corrige metadados e traduz BUFFER_WBINVL1/SC para barreira de memória existente. |
| `a808e762` | Aceita S_SLEEP como indicação de escalonamento, sem emular o atraso. |
| `ab1dd384` | Emite inteiros indefinidos de 64 bits em SPIR-V. |
| `d9cf41ba` | Preserva a operação InverseBallot quando uma constante não pode ser simplificada, emitindo aviso em vez de abortar. |
| `78bedfac` | Preserva arestas de continuidade no fluxo de controle dos shaders. |

A geração local de binários de shaders passou de 33 para 34 para invalidar
binários antigos. As versões locais não foram substituídas pelos números do upstream.
A correção `612713d5` de comparação de invocações de geometria já estava presente.

## Validação

- Compilação incremental de `bbgpu` com Ninja, RelWithDebInfo, PGO off e LTO OFF: passou.
- `git diff --check`: passou.
- Primeiro grupo de seis correções: execução de 600 segundos, 119 amostras de FPS,
  até 597 segundos; sem falha fatal ou perda do dispositivo Vulkan registrada.
  Usuário confirmou imagem, sombras, áudio e movimentação normais.
- Grupo final de sete correções: execução de 600 segundos, 119 amostras, até
  598 segundos; sem falha fatal ou perda do dispositivo Vulkan registrada.
  Usuário confirmou imagem e áudio normais. Últimas quatro amostras: 25,9,
  26,0, 25,7 e 25,4 FPS.
- Ambas encerraram pelo watchdog programado, com código 142.
- Testes com caches separados e configuração do launcher Linux PS4 Pro:
  limite 60 FPS, vblank 60 Hz, EOP defer 0, DMA 0, readback assíncrono 0,
  e arquivo de comandos com culling de índices e sombras desativado.
- Hashes dos dois arquivos com alterações locais no FSR permaneceram iguais.

Logs: `out/validacao-shadps4-recompiler/` e `out/validacao-shadps4-cfg/`.
Esses artefatos são locais e não versionados.
As rotas não foram controladas e os caches estavam frios; os resultados não
demonstram ganho de desempenho nem cobrem todas as cenas do jogo.

## Avaliação pendente

A triagem não cobre integralmente os 90 commits que tocam vídeo/recompilador
desde a base declarada. Correções de cache de texturas, fluxo CE/DE e barreiras
LDS exigem análise das adaptações locais antes de serem incorporadas.
Em particular, `08225c2b` não pode ser aplicado diretamente ao passe LDS local,
que contém tratamento próprio de ReadLane e sincronização entre subgrupos.
Nenhuma dessas mudanças amplas foi incorporada neste grupo.

## Experimento LDS suspenso

A adaptação de `08225c2b` apresentou `Guest fault (signal 11)` em `0x1a371`,
endereço nulo, após a amostra de 115 segundos (saída 139). Imagem e áudio
estavam normais. O controle sem essa adaptação completou 600 segundos,
até a amostra de 597 segundos, sem falha fatal registrada e encerrou pelo
watchdog (saída 142). Isso não identifica definitivamente a causa, pois esse
endereço de falha já apareceu anteriormente. A adaptação foi retirada das
fontes e arquivada em `out/validacao-shadps4-lds-singleton/candidate.patch`.

## Patch experimental fps60 e fullscreen

Com a biblioteca da main, sem a adaptação LDS, o patch fps60 foi aplicado
em memória (uma escrita de três bytes), com limite de host de 60 FPS,
PS4 Pro, fullscreen, EOP defer 0, DMA 0 e culling de índices/sombras desativado.
Foram realizadas execuções com vblank emulado em 120 e 60 Hz, ambas por
600 segundos, com 119 amostras e encerramento pelo watchdog, sem falha fatal
registrada. O usuário confirmou imagem, áudio e movimentação normais nas duas.
O teste em 60 Hz reutilizou o cache aquecido pelo teste em 120 Hz; as rotas
não foram controladas, portanto não há conclusão causal sobre desempenho.
Logs e resumos: `out/validacao-fps60-fullscreen/`.
A configuração dos próximos testes usa 60 Hz emulados, sem mudar o padrão
versionado do launcher.

## Expansão de texturas: 699009c9 (em validação)

Branch `integracao-shadps4-texture-expand`. A cópia da imagem antiga só ocorre
se ela contiver dados válidos modificados pela GPU, sem flags Dirty. A condição
local `SafeToDownload()` é equivalente a `HasGpuValidData()` do upstream.
Quando a cópia ocorre, o destino herda GpuModified e tem Dirty removido.
Nos outros casos, a atualização da memória do jogo não é sobrescrita.
A ordem local de liberação e rastreamento foi preservada. A mudança não
altera shaders e mantém sua geração em 34.

Validação: compilação incremental de bbgpu passou; diff sem erros de
formatação. Teste de 600 segundos em fullscreen, com patch fps60, limite de
60 FPS e vblank emulado de 60 Hz; 119 amostras até 596 segundos, sem falha
fatal ou perda do dispositivo Vulkan registrada. Encerramento pelo watchdog,
saída 142. Usuário confirmou texturas, imagem e áudio normais durante o teste.
Hashes dos arquivos com alterações locais no FSR permaneceram iguais.
Logs e resumo: `out/validacao-shadps4-texture-expand/`.
O teste é de estabilidade e compatibilidade; não comprova ganho de FPS.

## Preservação de sub-recursos: d3ff0e0c

Branch `integracao-shadps4-texture-subresources`. Na resolução de sobreposição,
quando a imagem existente é um sub-recurso da solicitada e a imagem maior
ainda não existe, ela é criada, registrada, atualizada e rastreada antes da
cópia do mip/slice existente. Depois da cópia, a imagem antiga é liberada.
Isso preserva conteúdo da GPU que a criação posterior a partir da memória
do jogo poderia perder. O caminho de render targets não foi alterado.

Adaptação do commit `d3ff0e0c` com o alocador local `slot_images.insert` e
`CheckImageSetOwner()`. A correção anterior de expansão permanece presente;
a alteração LDS continua excluída. Não há mudança de geração de shaders.
Compilação e teste em jogo registrados em
`out/validacao-shadps4-texture-subresources/`.
Compilação incremental e diff check passaram. Teste de 600 segundos em
fullscreen com patch fps60, limite de 60 FPS e vblank emulado de 60 Hz:
119 amostras até 596 segundos, sem falha fatal ou perda do dispositivo Vulkan
registrada. Encerramento pelo watchdog, saída 142. Usuário confirmou texturas,
sombras, efeitos e áudio normais. Arquivos locais modificados do FSR preservados.
Rotas não controladas; sem conclusão de ganho de desempenho.

## Operações atômicas em imagens 1D: 5ae2caf3

Branch `integracao-shadps4-image-atomics`. Corrige coordenadas de
OpImageTexelPointer em operações atômicas U32, F32 e compare-and-swap.
Imagens Color1D recebem coordenadas (x, 0); Color1DArray recebe (x, 0, slice),
compatíveis com a representação 2D usada pelo backend. Outros tipos passam
sem transformação. Correção do upstream aplicada sem alterações funcionais.
A geração de shaders avança de 34 para 35. A alteração LDS permanece excluída.
Esta geração 35 não deve reutilizar o cache do experimento LDS, que usou o
mesmo número em uma biblioteca não publicada; o teste usa cache separado.

Logs: `out/validacao-shadps4-image-atomics/`. Compilação incremental e diff
check passaram. Execução de 600 segundos com cache separado, fullscreen,
patch fps60, limite de 60 FPS e vblank emulado de 60 Hz: sem falha fatal ou
perda do dispositivo Vulkan registrada; última amostra aos 597 segundos.
Encerramento pelo watchdog, saída 142. Usuário confirmou texturas, efeitos
e áudio normais. Alterações locais do FSR preservadas.
Um teste geral do jogo não garante cobertura de atomics em imagens 1D.

Na revisão de cópias Vulkan, `b3d46e96` foi adiado: o dimensionamento local
do buffer temporário cobre apenas o nível base e precisa ser ampliado junto
com a cópia de todos os mipmaps. O caminho local também contém proteção
contra cópias incompatíveis entre formatos de profundidade; não deve ser
substituído diretamente pelo upstream. Correções de índices nulos exigem
revisar o caminho local de buffers antes de adaptação.

## Escopo EXEC após branch vazio: c34ca21f

Branch `integracao-shadps4-exec-scope`. Ao descartar um escopo vazio, mantém
o início do próximo escopo se a instrução também abre um novo escopo, em vez
de limpar incondicionalmente curr_begin. Patch upstream de uma linha aplicado
sem alterações funcionais. A geração local de shaders avança de 35 para 36.
Não inclui o experimento LDS. Logs em `out/validacao-shadps4-exec-scope/`;
teste com cache separado. Compilação incremental e diff check passaram.
Execução de 600 segundos em fullscreen, com patch fps60, limite de 60 FPS
e vblank emulado de 60 Hz, sem falha fatal ou perda do dispositivo Vulkan
registrada; última amostra aos 596 segundos. Encerramento pelo watchdog,
saída 142. Usuário confirmou imagem, efeitos, sombras e áudio normais.
Arquivos locais modificados do FSR preservados. Sem conclusão de ganho de FPS.

Triagem adicional: as mudanças de gradientes/offsets 1D (`e754ce62`), SampleId
KHR (`e0cd957a`), tipo do resultado de cube-face (`4cbd23ef`) e instruções
V_MIN_F64/V_TRUNC_F64 (`282f6445`, `53af37af`) já têm implementação local
correspondente e não foram reaplicadas. Isso não significa equivalência
integral entre o recompilador local e a versão upstream.

## Cópias entre contagens de camadas distintas: afde6318 (em validação)

Branch `integracao-shadps4-copy-layers`, baseada na main sem CLAMP/LDS.
CopyImageWithBuffer já calcula min(src.layers, dst.layers); o upstream remove
a exigência redundante de igualdade das contagens, mantendo a restrição de
um único mip. A adaptação local permite esse caso também na seleção do
caminho intermediário para formatos de profundidade diferentes, preservando
a proteção RDNA4 contra cópias diretas incompatíveis D32/D32S8.

O buffer temporário continua dimensionado pela contagem de camadas da origem,
que é maior ou igual ao mínimo copiado. Permanecem o limite inferior de 17 MiB,
alinhamento e uso de alocação dedicada sincronizada por tick. A geração de
shaders permanece em 36. Logs: `out/validacao-shadps4-copy-layers/`.
Teste de compatibilidade em jogo pendente; uma partida comum não garante
cobertura do caso de contagens distintas ou de todos os formatos de profundidade.

Execução de 600 segundos concluída pelo watchdog (saída 142), com 119 amostras
até 597 segundos, sem falha fatal ou perda do dispositivo Vulkan registrada.
Usuário confirmou imagem e áudio normais durante o teste. O resultado não
comprova ganho de desempenho nem cobertura específica das contagens distintas.

## Cópia de múltiplos mipmaps: b3d46e96

Branch `integracao-shadps4-copy-mips`, baseada na main sem CLAMP/LDS.
A adaptação cria uma única lista de regiões e calcula o tamanho em 64 bits,
usando todos os níveis e camadas comuns. Os offsets relativos são alinhados
a 16 bytes e somados ao offset real da alocação. O tamanho reservado cobre
o maior dos dois formatos em cada nível; cópia e alocação usam o mesmo layout.
O runtime verifica que o intervalo cabe no buffer antes de emitir comandos.

Mantidos as barreiras de transferência, o piso de 17 MiB, o alinhamento da
alocação a 256 bytes e o caminho intermediário RDNA4 para formatos de
profundidade diferentes. Esse caminho agora também atende múltiplos mips.
Não altera shaders e mantém sua geração em 36.

Compilação incremental de bbgpu passou. Teste local de layout passou com
nível único, dimensões ímpares, camadas, offset de alocação não zero, D32/D32S8
nos dois sentidos, blocos BC1, volumes 3D e cálculo acima de 4 GiB:

```sh
c++ -std=c++20 -Igpu/shadps4 tests/test_buffer_copy_layout.cpp -o out/validacao-shadps4-copy-mips/test-buffer-copy-layout
out/validacao-shadps4-copy-mips/test-buffer-copy-layout
```

Esses testes verificam layout e dimensionamento, sem emitir comandos Vulkan.
Teste controlado de 600 segundos concluído em fullscreen, patch fps60, limite
de 60 FPS e vblank emulado de 60 Hz: 119 amostras até 596 segundos, sem falha
fatal ou perda do dispositivo Vulkan registrada. Encerramento pelo watchdog,
saída 142. Usuário confirmou imagem e áudio normais. FSR preservado.
O teste do jogo não garante cobertura de todos os casos multi-mip na GPU;
o teste local de layout complementa a verificação, sem substituir validação
Vulkan específica. Não há conclusão de ganho de desempenho.
Logs: `out/validacao-shadps4-copy-mips/`.

## Reavaliação FMASK com orçamento Neo: 14ada48a (em preparação)

Branch `reavaliacao-shadps4-fmask-5376`. Patch upstream de uma linha:
EliminateFastClear é chamado antes de ignorar FmaskDecompress. A função
existente verifica alvo válido, fast_clear e metadados pendentes antes de limpar.
Não muda os shaders. O teste anterior com 5056 MiB falhou em 0x1a371;
posteriormente a mesma assinatura foi reproduzida na main sem esse patch,
com bitmap zerado, portanto a causa não foi atribuída a FMASK.

Esta reavaliação usa 5376 MiB, orçamento agora padrão do launcher PS4 Pro,
e mantém os demais parâmetros do teste de demonstração sem interação.
O teste será realizado com uma cópia preservada do loader de diagnóstico
para capturar a tabela se a falha voltar; os diagnósticos não são incorporados
nesta branch. A biblioteca GPU é a desta branch. Logs, loader e seu hash
ficam em `out/validacao-shadps4-fmask-5376/`. Teste controlado ainda não iniciado.
Ausência de falha não comprova cobertura específica de todas as passagens FMASK.

O teste autorizado completou 600 segundos pelo watchdog (saída 142), com
119 amostras até 596 segundos, sem falha fatal ou perda do dispositivo Vulkan
registrada. O log confirma Neo, 5376 MiB e zero memória de depuração, mas não
registra marcadores st_gameflow; usuário confirmou demonstração, imagem,
cores, sombras e áudio normais. Não há conclusão de ganho de desempenho ou resolução
definitiva da falha intermitente.

## IMAGE_GATHER4_C_L: 3a9f5726

Branch `integracao-shadps4-gather4-cl`, baseada na main com orçamento PS4 Pro
5376 MiB. O teste isolado não incluiu FMASK/CLAMP/LDS. Adiciona a instrução IMAGE_GATHER4_C_L ao
dispatch já existente de IMAGE_GATHER, conforme patch upstream de uma linha.
O caminho compartilhado interpreta os modificadores de comparação e LOD;
esta alteração não introduz um tradutor separado.

A geração local de shaders avança de 36 para 38 para não compartilhar a
geração 37 do experimento CLAMP ainda não integrado. O teste usou
cache separado e 5376 MiB. Logs: `out/validacao-shadps4-gather4-cl/`.
O teste geral de partida não demonstra uso dessa instrução específica
nem cobertura de todos os shaders.

O teste autorizado posterior completou 600 segundos pelo watchdog (saída
142), com 119 amostras até 596 segundos, sem falha fatal ou perda do dispositivo
Vulkan registrada. Usou demonstração sem interação, 5376 MiB, fullscreen,
patch fps60 e cache separado; loader de diagnóstico preservado e biblioteca
GPU desta branch. O log não contém marcadores st_gameflow. Usuário confirmou
demonstração, imagem, sombras e áudio normais; não comprova cobertura da instrução específica.

Após a confirmação dos dois testes isolados, a branch gather foi atualizada
com a main contendo FMASK; a combinação compilou, mas não houve novo teste
controlado da combinação nesta etapa. CLAMP e LDS continuam excluídos.

## Padrão adicional de descritor de buffer: 8bafaa5a (em preparação)

Branch `integracao-shadps4-buffer-sharp-pattern`. Reconhece o padrão que
limpa stride do descritor e desloca seu número de registros, preservando a
transformação como pós-operação do fetch. Patch upstream aplicado nos quatro
arquivos de descoberta, dados e aplicação do descritor. O operando imediato
de S_LSHL_B32 é mascarado a 5 bits na tradução existente.

BufferResource é parte dos metadados persistidos como estrutura binária;
o novo campo e a nova enumeração exigem invalidar o cache. Geração binária
avança de 38 para 39 e geração de metadados de 22 para 23.

Compilação incremental passou. Teste local de GetSharp passou: descritores
imediatos e carregados do flat buffer, preservação de endereço e flags,
ausência de alteração da fonte, shift zero e recurso inválido. Comando:

```sh
c++ -std=c++23 -O2 -Igpu/shim -Igpu/shadps4 tests/test_buffer_sharp_postop.cpp -o out/validacao-shadps4-buffer-sharp/test-buffer-sharp-postop
out/validacao-shadps4-buffer-sharp/test-buffer-sharp-postop
```

O teste não valida sozinho o reconhecimento do padrão na IR nem cobertura
de shaders do jogo. Teste controlado pendente, com cache separado e 5376 MiB.
Logs: `out/validacao-shadps4-buffer-sharp/`. FSR preservado.

O teste controlado autorizado completou 600 segundos pelo watchdog (saída
142), com 119 amostras até 597 segundos, sem falha fatal ou perda do dispositivo
Vulkan registrada. Usou 5376 MiB, fullscreen, patch fps60, vblank emulado
60 Hz e cache separado, com loader de diagnóstico preservado e a biblioteca
GPU desta branch. Não houve marcadores st_gameflow no log. O usuário autorizou
prosseguir após o encerramento; não forneceu avaliação visual e de áudio
explícita desse teste. A validação objetiva não comprova cobertura específica do padrão.
