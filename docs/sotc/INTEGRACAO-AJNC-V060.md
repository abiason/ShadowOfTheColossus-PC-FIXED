# Integração seletiva AjncSystem 0.60 — estabilidade, 60 FPS e atomics

Data: 2026-10-23. Base local: `233c8f82` (`0.59.1-linux.4`).
Branch de trabalho: `integracao-ajnc-v0.60-estabilidade`.

## Alterações implementadas

- `BufferCache::GatherDownloads`: `SOTC_RB_HOT` passa de 2 para 0 por padrão.
  Readbacks de regiões solicitadas pelo jogo continuam funcionando. As cópias
  especulativas adicionais ficam desativadas: uma região lida antes pode ter
  sido reutilizada para texturas ou heaps quando a cópia antiga chega.
  `SOTC_RB_HOT=1/2` ainda permite experimentos explícitos.
  Essa opção é independente de `SOTC_RB_ASYNC=0` do perfil Linux.
- `SotcLod::Collect`: proteção contra esgotamento do pool de páginas das
  texturas, com a histerese da 0.60.4. A cada 30 relatórios, com streaming
  de alta qualidade habilitado (`SOTC_LOD_LINGER>0`), pede um mip mais grosso
  abaixo de 8% livres e dois abaixo de 3%. O retorno ao nível mais fino exige
  mais de 16% livres, evitando alternância constante de detalhe.
  Não habilita alta qualidade automaticamente nem muda o padrão de linger.
- Leitura do bitmap pela memória de backing, com checagem de ponteiros,
  tamanho e overflow; ignora bits de preenchimento além da quantidade de
  páginas. Pool indisponível preserva o nível atual. `SOTC_LOD_POOL_LOW=0`
  desliga a proteção; `SOTC_LOD_LEVEL` continua disponível para diagnóstico.
  O nível de mip fica limitado a 14, preservando 15 como marcador de banco
  não utilizado.
  A revisão posterior substituiu a validação apenas dos endpoints por
  cópias delimitadas por cada VMA. Endpoints fisicamente contíguos não
  garantem que os bytes intermediários estejam mapeados ou usem o mesmo
  backing: um novo teste reproduziu a aceitação incorreta antes da correção.
  A leitura agora respeita lacunas e remapeamentos intermediários, aceita
  fragmentos físicos válidos e conta o bitmap em blocos de até 4 KiB.
  Se qualquer bloco falha, retorna pool indisponível, sem contagem parcial.
  A prioridade de streaming também passa a multiplicar a contagem em 64
  bits antes de saturar no campo de 24 bits. Um teste reproduziu que
  `0x1000000` amostras recebiam prioridade zero pela multiplicação anterior
  de 32 bits; agora recebem a prioridade máxima, como as demais contagens
  acima do limite. Não há medição de ocorrência desse caso em gameplay.
- `fps60game`: adiciona os três patches de alvo interno e a cvar
  `TargetFramesPerSeconds=1` da upstream. O checkbox de 60 FPS do launcher
  usa esse modo; o runner configura vblank e apresentação para 60 Hz/FPS,
  inclusive no Windows. Configurações explícitas do runner prevalecem.
  `fps60` continua sendo o desbloqueio legado, com os defaults anteriores.
  Cada instrução é conferida antes de gerar os arquivos; selecionar os dois
  modos juntos é rejeitado. Geração validada contra o `eboot.bin` EU 1.01
  local, sem modificar o original. Continua experimental: sem teste de física.
- Atomics float min/max de buffers: correção local do mesmo defeito descrito
  na 0.60, usando ramos SPIR-V exclusivos com `OpPhi` no fallback. `OpSelect`
  executava ambas as operações com efeitos na memória, alterando também o
  valor retornado. Caminho com extensão nativa permanece direto. Cache binário
  de shaders passa de 40 para 41 para rejeitar resultados antigos; metadados
  continuam em 23. Não é um cherry-pick do arquivo upstream de atomics,
  que não pôde ser obtido.
- Inventário de heaps para Linux (`runtime_heap_watch.c`), inspirado no
  diagnóstico Windows do commit upstream `568547d8`, disponível no histórico
  Git local. `SOTC_HEAP_WATCH=1` liga amostras a cada cinco segundos da tabela
  EU 1.01 em `image+0x2dfaab0`, antes exclusiva do monitor upstream Windows.
  Registra ID, endereço, classe, base, tamanho e, quando a estrutura é válida,
  páginas livres/total. Ausência de leitura não é tratada como pool vazio.
  Não descobre automaticamente qual classe deve receber a guarda de escrita
  nem ativa `BpeHeapGuard` no Linux.
- Journal de eventos do launcher em `user/events.log`, JSON por linha,
  disponível no fluxo gráfico e em `--play`. Registra sessão, horário UTC,
  PID do runner, opções solicitadas, sistema (CPU/RAM/disco quando
  disponíveis), início/fim do processo, parada pelo usuário, montagem de
  saves, sinais de carregamento já emitidos pelo runtime, desempenho e erros.
  É uma adaptação local da ideia da 0.60.6, sem copiar seu logger nativo.
  O ambiente completo não é gravado: apenas variáveis de jogo selecionadas.
  As opções são as solicitadas pelo launcher, não uma certificação dos
  valores finais resolvidos pelo runtime.
  São mantidos `events.log`, `events.1.log` e `events.2.log`, até 2 MiB cada.
  Desempenho é registrado no primeiro relatório e, depois, no máximo uma vez
  por minuto; erros repetidos têm limite de 100 por sessão. Falha ao gravar
  esse journal não impede iniciar o processo. `last_run.log` e cópias de
  crash continuam existentes. O novo módulo e estas notas entram no pacote
  Linux; a CI também verifica a sintaxe do módulo.
- Esperas cooperativas do processador de comandos: depois de uma rodada
  completa pelas filas mapeadas sem pacote novo, callback ou submissão
  concluída, chama `std::this_thread::yield()`. Pacotes CE, gráficos e compute
  e callbacks são registrados como progresso por um contador local à thread,
  sem operação atômica por pacote. Evita manter o polling contínuo quando
  as corrotinas só aguardam um registro/fence. `SOTC_CP_YIELD=0` restaura o
  comportamento anterior; o estado é emitido no log e capturado no journal.
  Adaptação local da política descrita na PR #198; o diff completo da PR
  não pôde ser obtido. O timeout de 2 ms do recorder Windows já existia
  localmente; o recorder não foi alterado neste lote.

Fontes consultadas:

- [Release 0.60.6](https://github.com/AjncSystem/ShadowOfTheColossus-PC/releases/tag/v0.60.6):
  desativação das cópias especulativas e regressões das otimizações.
- [PR #191](https://github.com/AjncSystem/ShadowOfTheColossus-PC/pull/191):
  pressão do pool de páginas e falha `0x1a371`.
- [Release 0.60.4](https://github.com/AjncSystem/ShadowOfTheColossus-PC/releases/tag/v0.60.4):
  histerese para evitar blocos ciano e vegetação piscando.
- [Cabeçalho de LOD upstream](https://raw.githubusercontent.com/AjncSystem/ShadowOfTheColossus-PC/main/gpu/shadps4/video_core/sotc_lod_stats.h):
  algoritmo de pressão e histerese adaptado à base local, sem dependência
  de `SotcLive` e mantendo as operações atômicas existentes.
- [Modos do jogo upstream](https://raw.githubusercontent.com/AjncSystem/ShadowOfTheColossus-PC/main/scripts/sotc_modes.py):
  endereços e instruções de `fps60game`.
- [Release 0.60](https://github.com/AjncSystem/ShadowOfTheColossus-PC/releases/tag/v0.60):
  descrição da correção de atomics e das mudanças de timing.
- [PR #215, diff](https://github.com/AjncSystem/ShadowOfTheColossus-PC/pull/215/files):
  consultada para comparar com a arquitetura de warm-up já presente localmente.
- [Commit 568547d8](https://github.com/AjncSystem/ShadowOfTheColossus-PC/commit/568547d8bcb0a22e8ee825b76c00c4e96d68d0a2):
  consultado pelo Git local; tabela de 48 heaps e campos do inventário.
- [PR #198](https://github.com/AjncSystem/ShadowOfTheColossus-PC/pull/198):
  política de espera para CPUs com poucos threads, adaptada à arquitetura
  local de filas/corrotinas.

O acesso Git a `ajnc` falhou por DNS (`Could not resolve host: github.com`).
O código acima foi adaptado a partir das fontes acessíveis pelo navegador;
não é um cherry-pick nem uma atualização integral para a tag 0.60.6.

## Validação

- Build incremental de `bbgpu` e `atomic-float-shader-test`: sucesso.
  Configuração local existente: RelWithDebInfo, PGO off, LTO off.
- Build de `sotc-cp-wait-test` e recompilação das unidades dependentes de
  `Liverpool`: sucesso. Teste compila com asserts habilitados e warnings
  como erros no código da fixture; os headers do renderer entram como
  headers de sistema para não alterar avisos preexistentes do código importado.
- Loader com o novo runtime recompilado em
  `out/validacao-ajnc-v060/bb-probe`; 14 testes do loader passaram contra
  esse binário, antes de atualizar `out/bb-probe`.
- Seis testes executam o cabeçalho real com um pool sintético:
  pressão e recuperação, histerese, mapa inválido/ausente, bitmap com bits
  de preenchimento, proteção desligada, streaming desligado e mip limite.
  O caso novo cobre uma lacuna com endpoints válidos, um remapeamento no
  meio com endpoints ainda contíguos, backing fragmentado válido, bitmap
  com mais de um bloco e falha depois de um primeiro bloco completo.
  O teste de prioridade verifica uma contagem pequena, a saturação normal
  e o valor elevado que reproduzia o overflow.
- 41 testes de launcher, runner, dependências e pacote Linux: sucesso,
  incluindo timing de `fps60game`, overrides e modo legado.
  O teste adicional importa o launcher extraído de um arquivo empacotado,
  com Python isolado e sem os caminhos do checkout.
- Seis testes de geração de modos: sucesso. Cobrem os três alvos, cvar,
  instrução inesperada em cada site, legado, versão incompatível,
  combinação rejeitada e geração sem modo de FPS.
- Dois testes de atomics: quatro módulos reais (min/max nativo e fallback)
  aceitos por `spirv-val --target-env vulkan1.3`; interpretação dos caminhos
  gerados em 128 combinações de valores positivos, negativos, zeros com
  sinal e infinitos. Uma escrita por chamada, valor final correto e retorno
  dos bits anteriores. Não valida comportamento de NaN ou execução no driver.
- 14 testes existentes do loader: sucesso.
- Sete testes de inventário: seis passaram, cobrindo contagem, bits de
  preenchimento, u32 em +0x58, limites, leituras parciais, mapas separados,
  lacunas entre VMAs e ponteiros inválidos. O adaptador de memória foi
  exercitado com leitor de host injetado; a integração com a leitura real
  do kernel foi pulada por `EPERM` em `process_vm_readv` da própria memória.
  Uma sonda independente confirmou `result=-1 errno=1` neste ambiente.
- Treze testes de journal: sucesso, com processos Python reais simulando
  sucesso/falha; fluxo gráfico sem Tk para parada/falha de lançamento;
  rotação UTF-8, escrita concorrente, intervalo de desempenho, configuração
  inválida e armazenamento indisponível. Nenhum processo do jogo é aberto.
  Executados também com `ResourceWarning` tratado como erro; os pipes de
  saída agora são fechados após a leitura.
- Cinco testes novos usam a thread e as corrotinas reais de `Liverpool`,
  com PM4 `WAIT_REG_MEM` e NOPs: gráficos bloqueados, compute bloqueado com
  fila gráfica vazia, retorno explícito ao polling, pacotes ativos sem
  chamadas de yield e thread de comandos/callback compartilhando um único
  núcleo por afinidade do processo de teste. Todos passaram. O teste
  interpõe `sched_yield` para observar a chamada real da biblioteca e
  libera as esperas por callbacks enviados ao próprio CP, sem acessar
  registradores concorrentemente de fora da thread.
  A CI executa esse grupo após compilar o binário, sem exigir dispositivo
  Vulkan. O stub de `runtime_disabled_optimizations` foi alinhado ao tipo
  real de 64 bits; os dois testes de atomics passaram novamente.
- Suíte `test_sotc_*.py`: 102 testes, 101 aprovados e um skip explícito da
  leitura de memória pelo kernel. Os grupos de loader (14) e atomics (2)
  acima também passaram separadamente nos lotes anteriores.
- `git diff --check`: sucesso.
- `out/bb-gpu-capabilities`: saída 1, `GPU scene scaling: no Vulkan device`.
  Sem validação de gameplay, artefatos visuais, áudio ou desempenho naquele
  ambiente de build; o teste posterior em sessão gráfica está descrito abaixo.
  O build usa o estado local preexistente do submódulo FSR;
  suas alterações não foram editadas nem incorporadas a este lote.

Reprodução dos testes novos, sem jogo ou GPU:

```sh
python3 -m unittest discover -s tests -p 'test_sotc_lod.py' -v
python3 -m unittest discover -s tests -p 'test_sotc_modes.py' -v
ninja -C out/gpu -j2 bbgpu atomic-float-shader-test
python3 -m unittest discover -s tests -p 'test_atomic_float_shaders.py' -v
python3 -m unittest discover -s tests -p 'test_sotc_heap_watch.py' -v
python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_sotc_events.py' -v
python3 -m unittest discover -s tests -p 'test_sotc_*.py' -v
ninja -C out/gpu -j2 sotc-cp-wait-test
python3 -m unittest discover -s tests -p 'test_sotc_cp_wait.py' -v
```

Os logs locais estão em `out/validacao-ajnc-v060/`. A redução de FPS descrita
na upstream não constitui medição deste fork.
Os testes de espera cooperativa demonstram retomada, conclusão e chamadas
ao escalonador nas fixtures; não medem ganho de FPS, consumo de CPU do jogo
ou latência de frames em hardware real. Esperas internas que não retornam
ao escalonador de corrotinas também não são resolvidas por essa política.

## Validação do pacote preview em sessão gráfica — 2026-10-23

Pacote `SotC-PC-linux-x86_64-e7e679f64ad3-20ca024e9d9f`, com hash
verificado na preparação. Execução PS4 Pro, fullscreen, 5376 MiB de memória
direta, `SOTC_EOP_DEFER=0`, `SOTC_RB_ASYNC=0`, dados de usuário isolados.

- Perfil 30 FPS: 600 segundos, 119 amostras até 597 s; média 29,81 FPS,
  mínima 26,5 e máxima 30. Imagem, áudio e controles confirmados pelo usuário.
- Encerramento pelo watchdog solicitado (`--timeout 600`, SIGALRM, saída
  142); o dump de threads ao final acompanha essa parada programada.
  Sem assertion GPU, perda de dispositivo ou segfault registrado.
- A tentativa anterior dentro do sandbox parou sem dispositivo de vídeo
  SDL; a execução com acesso à sessão gráfica inicializou normalmente.
- Resultado e log: `out/teste-gameplay-preview-atual/resultado-30fps-retomada.json`
  e `game-30fps-retomada.log` no mesmo diretório.

São amostras periódicas, sem comparação controlada de desempenho com a
release anterior. Esta sessão não valida a transição após os créditos,
a guarda de pool com alta qualidade habilitada ou o monitor de heaps.
O perfil de 60 FPS usou `fps60game`, com os três patches de instrução
e `TargetFramesPerSeconds=1` confirmada no log. Completou 600 segundos:
119 amostras até 596 s, média 53,25 FPS, mínima 23 e máxima
60. Encerramento programado por SIGALRM (142), sem os marcadores
de falha fatal acima. O usuário confirmou imagem, áudio, controles e
velocidade dos movimentos normais nesta sessão. Não houve confirmação
específica de escalada e saltos nos colossos ou da transição após os créditos.
O perfil não sustenta 60 FPS constantes; as duas sessões não
foram uma comparação controlada do mesmo percurso. Resultado e log em
`resultado-60fps-retomada.json` e `game-60fps-retomada.log`, no mesmo diretório.

### Sessão estendida com cópias dos saves

O mesmo preview completou 1800 segundos em `fps60game`, fullscreen,
com `SOTC_HEAP_WATCH=1` e cópias dos três slots de progresso. Foram 358
amostras até 1794 s: média 49,87 FPS, mínima 20,1 e máxima 60; média do
último minuto 59,48 FPS. Encerramento programado por SIGALRM (142), sem
assertion GPU, perda de dispositivo ou segfault registrado. Os hashes dos
saves originais permaneceram iguais. O usuário confirmou funcionamento
normal de escalada e saltos no colosso e da transição após os créditos
nesta sessão. Essa confirmação registra
o resultado observado; não prova ausência da falha em outros saves ou sessões.

O monitor Linux iniciou e leu objetos de heaps durante gameplay; houve
amostras com `readable=1` e `page_pool=unavailable`. Isso confirma acesso
real aos objetos, mas não valida a interpretação do pool dessas classes
nem a proteção contra esgotamento. Resultado e log locais:
`out/teste-gameplay-preview-atual/resultado-colossos-final-60fps.json`
e `game-colossos-final-60fps.log` no mesmo diretório.

### Investigação de `page_pool=unavailable`

O monitor agora acrescenta `reason` e os campos candidatos lidos em +0x50,
+0x58 (u32) e +0x60: `candidate_bitmap`, `candidate_words`,
`candidate_pages`. Os motivos distinguem endereço/objeto ilegível, contagens
incompatíveis, endereço do bitmap inválido e falha na leitura do bitmap.
Os candidatos são dados brutos; não são contagens de pool validadas.

Na captura com o loader diagnóstico, os objetos estavam legíveis, mas os
campos candidatos eram incompatíveis com o layout proposto: bitmap zero,
páginas zero ou `UINT64_MAX`, com rejeições `word-count-invalid` e
`page-count-invalid`. A leitura da memória, portanto, não explica essas
rejeições. O layout de cada classe ainda precisa ser identificado antes de
contar páginas; não interpretar indisponibilidade como esgotamento.
Os sete testes do inventário passaram fora do sandbox, incluindo o leitor
real do kernel e verificações dos motivos/candidatos sem contagens parciais.
Log local: `out/teste-gameplay-preview-atual/game-heap-diagnostics.log`.

### Pools do alocador de páginas identificados

A análise local das instruções EU 1.01 distingue a tabela de objetos de heaps
(`image+0x2dfaab0`) do estado do alocador de páginas, apontado pelo global
`image+0x2dfca78`. O inicializador em +0x18c94 e a seleção em +0x1a19f
estabelecem três descritores em +0, +0xa0 e +0x140; a estrutura em +0x1e0
é uma lista diferente e foi excluída após inspeção do inicializador.
O caminho +0x1a2f8 lê bitmap em +0x50, palavras u32 em +0x58 e páginas
em +0x60 do descritor. Ele procura bits ligados e limpa os bits alocados,
confirmando que bit ligado significa página livre nesse caminho.

O monitor passa a emitir `SOTC PAGE POOL` separadamente. A versão final
confere também as instruções de leitura em +0x1a2f8 antes de iniciar.
Em execução, os descritores 1 e 2 produziram contagens válidas em bitmaps
de 86.000 páginas; o descritor 0 estava sem bitmap inicializado. Foram
observadas contagens zero válidas no descritor 2 sem falha fatal nessa
captura curta; não inferir causa de falha nem somar pools como se fossem
reservas independentes. Amostras continuam concorrentes, sem snapshot atômico.

Oito testes passaram fora do sandbox, incluindo o leitor real, limites de
capacidade, raiz inválida, espaçamento e pools cheios/vazios. Loader final
recompilado; captura final curta com parada programada. Evidência em
`docs/validation/2026-10-23-page-pools.json`; logs completos locais em
`out/teste-gameplay-preview-atual/game-page-pools*.log`.
A descoberta das classes para a guarda de readback continua separada desse
inventário e não foi alterada.

### Classe BPE identificada; faixas de readback ainda pendentes

A tabela virtual EU 1.01 em `image+0x1595b70` contém as funções em
+0x48c80 e +0x493d0 nas entradas +0xa0/+0xa8. O caminho de liberação
+0x494a0 chama +0x495e0, o mesmo ponto usado pelo hook Windows.
O monitor confere endereço da tabela e ambas as entradas, via leitor seguro,
e acrescenta `bpe_class=verified range=undetermined`. Na captura real,
os slots 3, 7 e 18 foram identificados nessa classe.

A seleção de classe não habilita a guarda Linux. A inspeção de +0x49460
mostra `heap+0x28` passado como objeto ao caminho de callbacks em +0x45300;
o log já mostrava o mesmo valor em heaps distintos. Portanto, tratar
`[heap+0x28, heap+0x28 + heap+0x30)` como faixa própria do heap, como faz
a guarda importada, não está validado. Os rótulos históricos `base` e
`bytes` do inventário devem ser lidos como campos brutos +0x28 e +0x30,
não como uma faixa comprovada. Antes de portar a seleção da guarda, mapear
as regiões efetivamente pertencentes a cada heap e testar preservação dos
metadados sem suprimir dados válidos do jogo.

Loader diagnóstico compilado e nove testes passaram fora do sandbox.
Captura curta em `out/teste-gameplay-preview-atual/game-bpe-class.log`;
resumo versionado em `docs/validation/2026-10-23-bpe-class.json`.

### Listas de regiões gerenciadas — 2026-10-24

O caminho +0x479ce liga descritores à lista cujo sentinela é `heap+0x38`;
`heap+0x48` aponta ao primeiro nó, `+0x40` ao último e `+0x58` é a contagem
u32. Cada nó contém identidade em +0, anterior em +8, próximo em +0x10,
dono/sentinela em +0x18, tamanho em +0x58 e base em +0x60. O caminho BPE
+0x4898e usa base e tamanho desse descritor para criar os headers da região.

O monitor lê até 1024 descritores por heap, valida vínculos nos dois sentidos,
contagem, alinhamento de 64 KiB, limites e ausência de sobreposição, e relê
os campos da lista ao final. Qualquer falha devolve contagem zero com motivo,
sem publicar uma lista parcial como válida. Continua sendo uma amostra
concorrente, sem garantia de snapshot atômico ou proteção contra ABA.

A captura real confirmou listas válidas nos slots 3 e 7, com totais iguais
ao campo +0x30 naquele momento. O slot 3 tinha uma região de 150 MiB;
o slot 7 tinha centenas de regiões separadas, frequentemente de 1 MiB.
O slot 18 tinha lista vazia, mas +0x30 registrava 4 MiB. Portanto, a lista
não representa necessariamente toda a memória do heap: +0x48a10 aceita
blocos fornecidos por outro caminho e os liga a `heap+0xb8`. Esse caminho
externo ainda precisa ser mapeado antes de aplicar a guarda de readbacks.

Dez testes do inventário passaram fora do sandbox. Loader recompilado e
captura de 20 segundos sem alteração da guarda Linux; resultado em
`docs/validation/2026-10-24-bpe-regions.json`, log completo local em
`out/teste-gameplay-preview-atual/game-bpe-regions.log`.

### Regiões externas confirmadas — 2026-10-24

Os caminhos +0x489b8 (gerenciado) e +0x48a36 (externo) ligam o header
da região à cadeia em `heap+0xb8`. Esse header contém próximo em +0 e
marcador 3 em +8. Para regiões sem descritor gerenciado, o inventário anda
pelos headers físicos a partir de base+0x10: valida o ponteiro anterior,
avança por 16 + tamanho (flags baixas removidas) e aceita o fim apenas com
marcador 1 e tamanho zero. O limite inclui esse header terminal.

A leitura é limitada a 1024 regiões e 4096 blocos por região externa.
Rejeita ciclos, limites excedidos, headers ilegíveis/inconsistentes,
sobreposição e regiões gerenciadas ausentes da cadeia; relê a cabeça ao
final. Falhas retornam contagem zero com motivo. Essas verificações não
criam um snapshot atômico e ainda não autorizam uso concorrente pela guarda.

A captura confirmou o heap 18 com uma região externa de 4 MiB em
`0x115f370000`, enquanto a lista de descritores gerenciados estava vazia.
Os heaps 3 e 7 também produziram listas combinadas válidas com totais
coincidentes com +0x30 nas amostras observadas. Isso conclui a identificação
dos dois caminhos de regiões observados; não comprova estabilidade de
ponteiros após a amostra ou cobertura de outras versões do jogo.

Onze testes passaram fora do sandbox, incluindo blocos externos, cadeias
inválidas e descritores gerenciados ausentes. Loader recompilado; captura
curta em `out/teste-gameplay-preview-atual/game-bpe-external.log`, resumo
em `docs/validation/2026-10-24-bpe-external.json`. Próxima etapa: integrar
regiões e seleção de classe à guarda, com testes do renderer e da política
de invalidação/sincronização. A guarda Linux continua desativada.

## Uso do inventário de heaps no Linux

Com um build desta branch:

```sh
SOTC_HEAP_WATCH=1 python3 launcher/sotc_launcher.py
```

O launcher captura as linhas `SOTC HEAP` em `user/last_run.log`, no diretório
de usuário selecionado. Também é possível definir `SOTC_HEAP_WATCH=1` nas
variáveis extras do launcher. Sem essa opção não há thread nem varredura.
O diagnóstico não está no AppImage já publicado; exige o novo loader.

O leitor resolve cada VMA e usa a visão de backing, sem provocar readbacks
GPU. `process_vm_readv(getpid(),...)` evita uma falha do host se o endereço
desaparecer durante a amostra. Não há fallback para dereferência direta.
Imagem indisponível ou prólogo inesperado recusa a inicialização; uma
estrutura ou bitmap ilegível aparece como indisponível. A leitura da imagem
também está sujeita à política do kernel: no sandbox, o monitor recusa
iniciar porque a chamada de leitura é negada. Na retomada em 2026-10-23,
os sete testes de inventário passaram fora do sandbox, incluindo a integração
com `process_vm_readv` real. Isso valida o leitor do kernel nesse contexto;
a sessão estendida confirmou leitura dos objetos durante gameplay, mas
a interpretação dos pools ainda precisa de validação.

As amostras são concorrentes, não snapshots atômicos. Mesmo uma contagem
válida de zero páginas não prova a causa de uma falha. O próximo dado útil é
a lista de classes/endereços antes e depois de carregar a região final,
para validar a seleção e as faixas da guarda Linux.

## Pendências de integração

1. **Heaps criados pelo mundo:** a base Linux retorna zero em
   `runtime_sotc_heap()` (`src/probe.c`); o hook de descoberta é Windows.
   Antes de portar a proteção dos reservatórios distribuídos, é necessário
   obter o patch completo e implementar/testar a descoberta Linux. A guarda
   existente ainda pressupõe uma faixa contígua; não declarar a falha após
   os créditos corrigida por este lote.
   O inventário Linux leu objetos durante a sessão estendida, e o usuário
   confirmou transição após os créditos normal. Os pools do alocador foram
   identificados em estrutura separada; a seleção das classes para a guarda
   Linux identificou a classe BPE; a delimitação das regiões efetivas da guarda
   foi obtida pelos descritores gerenciados e pela cadeia externa. A integração
   dessas regiões à guarda, com sincronização e invalidação, continua pendente.
2. **Validação dos novos 60 FPS e atomics:** o preview completou dez minutos
   em cada perfil, com imagem, áudio e controles confirmados; no perfil 60,
   o usuário também confirmou velocidade normal dos movimentos. Na sessão
   estendida, confirmou escalada e saltos no colosso e transição após os
   créditos normais. A sessão não isola a execução do fallback de atomics
   no driver.
   A primeira abertura pode recompilar shaders por causa do cache binário 41.
3. **Pré-compilação paralela #215:** a análise inicial considerou apenas a
   criação dos workers usados durante gameplay após `WarmUp()`. A inspeção
   completa revelou um pool separado dentro de `WarmUp()`, controlado por
   `SOTC_PARALLEL_WARMUP` (padrão entre 1 e 12 threads). Portanto este fork
   já paraleliza o preload e espera os trabalhos antes de iniciar o jogo.
   A #215 usa outra arquitetura e permite gráficos terminarem depois do boot;
   não foi aplicada. Medir primeiro a implementação existente com cache do
   driver frio e cache do port preservado. Os tempos da PR não são resultados
   deste fork.
4. **Log de eventos:** implementado no launcher. Eventos de teclado,
   controle e todas as alterações do menu dentro do jogo ainda exigem
   instrumentação nativa e validação em execução; não foram implementados.
5. **Limpeza de texturas nos carregamentos e menu ao vivo:** ainda pendentes
   de integração e validação com o renderer. Não confundir montagem de save
   observada no log com um ponto comprovadamente seguro para liberar
   recursos Vulkan.

Manter fora do padrão as otimizações #219 e #232, texturas Máxima no PS4 Pro
e pré-leitura de todos os arquivos para a RAM, conforme a avaliação inicial.
Não substituir o orçamento de 5376 MiB validado no Linux por 9152 MiB.

Para validar este lote em hardware, comparar o mesmo save e câmera nos
perfis 30/60, com carregamentos repetidos, Santuário e região final. Separar
a execução padrão daquela com `SOTC_LOD_LINGER=1`, pois a proteção do pool
fica inativa quando os relatórios de alta qualidade estão desligados.
Medir FPS e uso de memória, observar corrupção visual e verificar transição
após os créditos; uma sessão curta sem falha não comprova esse último caso.
