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
