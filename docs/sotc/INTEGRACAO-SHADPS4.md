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
