# Diagnóstico da falha recorrente em 0x1a371

Estado: causa ainda não identificada; nenhuma correção causal aplicada.

A falha foi reproduzida sobre a main `4dd727f1` com apenas registro ampliado
de falhas, sem candidatos CLAMP, LDS ou FMASK. Isso demonstra que esses
candidatos não são necessários para a ocorrência; não determina quando ela
foi introduzida ou se podem influenciar sua frequência.

Na captura, `TRAP=13`, `ERR=0`, `si_code=128`. A instrução
`or (%r9,%r8,8),%rax` recebeu R9=0x1000213278, R12=-1 e
R8=0x3ffffffffffffff (R12 deslocado 6 bits à direita). O endereço resultante,
0x2000001000213270, não é canônico. O endereço nulo do relatório de sinal
não significa que R9 era nulo.

O código inicializa R12 em -1, busca bits em uma tabela e pode chegar à
leitura sem substituir a sentinela. Também pode produzir -1 quando um índice
excede o limite. Sem a tabela capturada, não há prova de qual caminho ocorreu
ou por que a busca não produziu resultado válido. As ocorrências registradas
estão próximas de mensagens de transição/início de partida, por volta de dois
minutos. A execução sob GDB completou 600 segundos sem reproduzir a falha;
o debugger altera temporização e tratamento de sinais.

## Captura sem GDB em preparação

`fault_snapshot.h` usa process_vm_readv sobre o próprio processo para ler
128 bytes do objeto em R14, até 64 KiB da tabela em R9 (contagem de palavras
limitada por RDX) e 256 bytes de stack. O handler registra leituras parciais,
erros, quantidade de palavras não nulas e bits ativos, prefixo da tabela e
campos do objeto. Leituras inválidas retornam erro em vez de serem feitas
diretamente pelo código do handler. Não usa alocação dinâmica nem modifica
a memória do jogo. Só coleta memória na falha fatal de offset 0x1a371.

As threads não são congeladas: alterações concorrentes podem afetar a
consistência da leitura. Páginas protegidas podem tornar a captura parcial
ou indisponível. Não habilita a guarda BPE do Windows: no Linux,
runtime_sotc_heap retorna zero; a relação dessa diferença com a falha não foi
estabelecida e o layout da guarda não deve ser presumido compatível.

Compilação do loader com PGO off/LTO OFF passou. O teste abaixo passou fora
do sandbox; dentro dele a leitura de memória foi bloqueada. Verifica handler
de sinal, leitura válida, endereço não canônico, páginas inacessíveis, leitura
parcial, limite de tamanho e overflow de endereço, sem executar o jogo:

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -Isrc tests/test_fault_snapshot.c -o out/investigacao-fault-1a371/snapshot-sem-gdb/test-fault-snapshot
out/investigacao-fault-1a371/snapshot-sem-gdb/test-fault-snapshot
```

Teste controlado com a nova captura completou 600 segundos sem falha fatal
ou perda do dispositivo Vulkan registrada, encerrando pelo watchdog com saída
142. Última amostra aos 596 segundos. A falha não ocorreu, portanto nenhuma
tabela foi capturada; isso não demonstra resolução do problema.
Log e resumo em `out/investigacao-fault-1a371/snapshot-sem-gdb/`.
Artefatos locais:
`out/investigacao-fault-1a371/`. Experimento FMASK arquivado em
`out/validacao-shadps4-fmask-clear/candidate.patch`; CLAMP permanece no PR #8
em rascunho. O submódulo FSR não faz parte do diagnóstico.

## Histórico de escritas (preparado, ainda sem teste controlado)

O projeto já possui um registro circular de escritas instrumentadas com
`BB_WRITE_LOG=1`. Ele é desligado por padrão. O dump foi adaptado para
incluir R8/R9 na busca de escritas próximas e para tolerar RAX inválido:
usa process_vm_readv no Linux e ReadProcessMemory no Windows ao imprimir
memória perto de RAX, sem ler diretamente endereços potencialmente inválidos.

Teste local Linux com RAX não canônico passou e verificou que uma escrita
instrumentada próxima de R9 é reportada. Compilação do projeto passou.
Teste e log em `out/investigacao-fault-1a371/write-log/`; comando de compilação:

```sh
c++ -std=c++20 -O2 -Wall -Wextra -Werror -Wno-error=extra -Igpu/shim tests/test_write_log_fault.cpp gpu/shim/bbport_write_log.cpp -o out/investigacao-fault-1a371/write-log/test-write-log-fault
out/investigacao-fault-1a371/write-log/test-write-log-fault
```

O aviso de enum em Record é preexistente e não foi alterado. O teste requer
process_vm_readv disponível, fora do sandbox que bloqueia essa operação.
O caminho Windows foi ajustado no código, mas não compilado ou executado aqui.

O registro cobre apenas pontos já instrumentados, tem histórico finito e
altera temporização; não observa todas as escritas da CPU. Nenhuma escrita
encontrada não absolve a GPU nem identifica a origem da tabela inválida.
Próximo teste proposto: main com diagnóstico, snapshot e BB_WRITE_LOG=1,
sem GDB e sem candidatos FMASK/CLAMP/LDS.

Esse teste completou 600 segundos pelo watchdog, saída 142, sem falha fatal
ou perda do dispositivo Vulkan registrada; última amostra aos 597 segundos.
Os totais periódicos confirmam o registro ativo de readbacks e fences/labels.
Como não ocorreu falha, não houve dump final da tabela ou do histórico circular.
Isso não prova resolução nem identifica a origem do índice inválido.
Log e resumo em `out/investigacao-fault-1a371/write-log-game/`.

## Reprodução controlada: protocolo em preparação

Comparação de sete logs: cinco execuções com falha e duas completas têm
duas mensagens st_gameflow() starting game. Nas cinco falhas, a segunda
transição antecede o encerramento; nas duas completas, a mesma transição
ocorre sem falha. Ela é um ponto de observação, não um gatilho suficiente.
Inventário local em `out/investigacao-fault-1a371/reproducao/comparacao-transicoes.json`.

Antes de repetir, identificar com o usuário se houve carregamento de save
ou demonstração automática. Fixar uma única sequência: modo selecionado,
save/cena ou demonstração, ações no menu, momento de carregar/reiniciar,
movimentos de câmera e interação com o controle. Usar a mesma biblioteca,
cache e diagnóstico, registrar os instantes das ações e preservar cada log.
Separar demonstração sem interação de carregamento e jogo manual em testes
distintos. Esses testes ainda não foram iniciados ou autorizados nesta etapa.
Não alterar simultaneamente cache, vblank, patch fps60 ou instrumentação.
