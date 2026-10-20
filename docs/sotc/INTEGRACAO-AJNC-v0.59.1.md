# Integração seletiva do AjncSystem v0.59.1

Relatório da etapa realizada em 20/10/2026 na branch `integracao-ajnc-v0.59.1`.
Base local: `d8716f81c9b61b56b56709322b0aa552b15acbcc`.
Referência upstream inspecionada: tag local `v0.59.1`, commit `2250f32`.
As mudanças descritas estão no diretório de trabalho, sem commit ou push.
Este conjunto não representa a integração completa da v0.59.1.

## Mudanças selecionadas

| Referência upstream | Adaptação local |
| --- | --- |
| `d9d5b77`, `2fdb0b5`, trecho de `a1b858e` | Diagnósticos de GPU, fabricante, driver, Vulkan, memória esparsa e subgrupos. A versão do driver é registrada após `CollectDeviceParameters()`. A seleção por `SOTC_GPU_VENDOR` não foi incorporada. |
| `12410ef` | Após as tentativas existentes e a coleta emergencial, tentar o tamanho solicitado na VRAM e depois na RAM. A mensagem não recomenda a opção Economy, ausente neste launcher. |
| `c6fd7dc` | Limitar duas mensagens repetitivas do recompilador a quatro ocorrências cada, com contadores atômicos. |
| `f9e2061` | Limitar avisos de metadados, preservando a condição local `SOTC_META_WARN` e usando contadores atômicos. |
| `b3b353c` | Separar o cache PS4 Pro com `_neo`, mantendo o sufixo `_nodma` e o caminho do modo normal. |
| `7200908` | Recusar binários diferentes sob o mesmo nome de permutação, comparando disco e gravações pendentes. Omitir metadados e novos registros de pipelines das permutações recusadas. |

### Proteção de binários de shaders

`ShaderBinaryStore` reserva o caminho e os bytes antes de submeter a gravação à fila.
Solicitações idênticas são aceitas sem outra gravação; conteúdo diferente é recusado.
A reserva é liberada após a publicação ou após recusa/falha da gravação.
Somente os binários pendentes são mantidos nessa estrutura.

A serialização identifica um binário pelo par completo `(pgm_hash, perm_idx)`,
evitando a combinação por XOR utilizada no upstream. Uma permutação recusada
continua disponível para uso em memória, mas não gera novos registros dependentes
no cache persistente nesta sessão.

A proteção considera a fila do processo atual e o cache em diretório, utilizado
por esta configuração. O caminho de cache arquivado mantém o comportamento
anterior. Não foi validada concorrência entre processos independentes.

## Preservações e adiamentos

- DMA continua desligado por padrão para todas as GPUs. `BB_DIRECT_MEMORY_ACCESS=1`
  continua sendo a opção explícita para habilitá-lo. `3718855` permanece adiado.
- Readbacks assíncronos continuam desligados por padrão. `9afd8e5` permanece adiado:
  a branch já possui a estratégia local `GiveToGuestWrite()`, diferente do upstream.
- Nenhuma alteração desta etapa no runtime de áudio, limite padrão de FPS,
  adaptações de `build.sh` ou correções Linux/RDNA4 previamente presentes.
- Não houve merge, atualização de submódulos, commit ou push.
- As alterações preexistentes de `gpu/third_party/fsr-vulkan` foram preservadas:
  dois arquivos, 110 inserções, ponteiro `c64f093`.

## Validação

Compilação Linux de `bbgpu` concluída após os lotes. `git diff --check` sem erros.
O teste `shader-binary-store-test` passou cobrindo:

- Colisão enquanto o trabalhador ainda não publicou o primeiro binário.
- Solicitações concorrentes com conteúdo idêntico e diferente.
- Comparação com arquivo existente após reabrir a estrutura.
- Recusa de arquivo com tamanho diferente, sem sobrescrevê-lo.
- Nova tentativa após recusa da fila ou falha de publicação.
- Recusa de destino indisponível.

Para executar o teste em um diretório novo:

```bash
cmake --build out/gpu --target bbgpu shader-binary-store-test -j 2
out/gpu/shader-binary-store-test "$(mktemp -d)/case"
```

Testes de execução na RX 9060 XT, RADV 26.2.4 / Vulkan 1.4:

| Teste | Duração programada | FPS registrados | Log local em `out/` |
| --- | --- | --- | --- |
| Diagnósticos | 120 s | 28,1–30,0 | `diagnosticos-v0591.log` |
| Recuperação de alocação, execução normal | 120 s | 27,6–30,0 | `validacao-arena-v0591.log` |
| Limites de mensagens | 120 s | 28,8–30,0 | `validacao-logs-v0591.log` |
| Readback assíncrono, apenas no processo de teste | 120 s | 28,0–30,0 | `validacao-readback-async-v0591.log` |
| Cache normal separado | 20 s | 29,6–30,0 | `validacao-cache-normal.log` |
| Cache Pro separado | 20 s | 27,9–30,0 | `validacao-cache-neo.log` |
| Proteção de shaders, cache inicialmente vazio | 45 s | 27,6–30,0 | `validacao-7200908-frio.log` |
| Proteção de shaders, reutilização do cache | 45 s | 28,1–30,0 | `validacao-7200908-quente.log` |

As execuções terminaram pelo timeout programado; os logs não contêm registros
fatais ou de perda do dispositivo. O PipeWire foi inicializado. O usuário confirmou
imagem e áudio no primeiro teste; as execuções seguintes foram avaliadas pelos logs.
Houve avisos Vulkan e de espera do runtime, portanto ausência de registros fatais
não significa ausência de avisos ou de possíveis problemas não observados.

No teste normal/Pro, foram criados `CUSA08809_nodma` e `CUSA08809_nodma_neo`
no cache de teste separado. Na reutilização do cache de shaders, os hashes SHA-256
dos 5.785 binários existentes permaneceram iguais, sem arquivos removidos.
Os logs e caches de teste são artefatos locais, não incluídos neste relatório.

## Limites dos resultados

- O caminho de recuperação por falta de memória não foi exercitado sob pressão real.
- As mensagens que receberam limites não ocorreram nas execuções observadas.
- O teste assíncrono não reproduziu a falha rara de proteção: `write refreshes`
  permaneceu zerado, embora `async joined` confirme o uso do caminho assíncrono.
- A colisão de binários pendentes foi exercitada no teste automatizado; os dois
  testes do jogo não registraram colisões. O teste automatizado cobre a reserva
  e publicação dos binários, não toda a serialização de metadados e pipelines.
- As amostras periódicas de FPS não substituem análise de frametime ou teste
  prolongado de jogabilidade. O teste curto do modo Pro valida a separação do cache.
- Windows e outras GPUs não foram testados nesta etapa.

O escopo desta etapa está concluído. Novos commits upstream devem ser selecionados
em um escopo separado, preservando os dois adiamentos acima.
