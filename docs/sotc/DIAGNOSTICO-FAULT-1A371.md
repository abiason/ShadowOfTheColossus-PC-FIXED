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

## Captura na demonstração automática sem interação

O teste autorizado desse protocolo falhou após a amostra de 115 segundos,
imediatamente após a segunda mensagem st_gameflow (00:01:56.20), saída 139.
Snapshot sem GDB, BB_WRITE_LOG=0, mesma main com diagnósticos e sem candidatos
CLAMP/LDS/FMASK. Leitura completa do objeto e stack; tabela de 1.264 palavras
(10.112 bytes) lida integralmente, sem erro e sem atingir o limite de captura.
Todas as palavras e bits lidos estavam zerados.

Objeto R14=0x1000000140: +0x50=0x1000213278 (tabela), +0x58=0x4f0
(1.264 palavras), +0x60=0x13bf0 (80.880), +0x68=0x13c00 (80.896).
A capacidade é consistente com 1.264 palavras de 64 bits. A busca não encontra
bits ativos, mantém R12=-1 e calcula endereço não canônico no acesso seguinte.
Isto explica o mecanismo do acesso inválido, mas não por que a tabela ficou
zerada. Snapshot concorrente não constitui histórico nem prova de corrupção;
esgotamento e problemas de atualização/liberação ainda precisam ser investigados.

Log, resumo e análise estruturada em
`out/investigacao-fault-1a371/reproducao-demo/`. Nenhuma correção causal ou
patch para ignorar a sentinela foi aplicado.

## Hipótese de orçamento e consultas de memória

O tamanho da tabela corresponde exatamente ao pool padrão do runtime:
5.056 MiB / 64 KiB = 80.896 bits, igual ao campo +0x68. O limite +0x60
exclui 16 páginas. A captura e o runtime sustentam essa associação, mas não
provam esgotamento: o estado dos mapeamentos e a atualização dos bits também
precisam ser examinados.

O helper do jogo em 0x1abf0 foi identificado por chamada e relocação: usa o
stub 0xf8f5c0, slot 0x16000d0, import rVjRvHJ0X6c, sceKernelVirtualQuery.
Ele consulta uma estrutura de 0x48 bytes e testa a flag committed (0x10),
depois atualiza o bitmap. A classificação de mapeamentos pode, portanto,
participar do problema; não se deve atribuir tudo à GPU ou à falta de orçamento.

Comparação proposta, ainda não executada: mesma demonstração sem interação,
mesma biblioteca/cache/diagnóstico e BB_WRITE_LOG=0, alterando somente
BB_DMEM_MB de 5056 para 6080 (mais 1 GiB). O parâmetro já existe e aceita
5056..16384 MiB; nenhum padrão será alterado. Se passar, isso pode indicar
mais margem, adiar o problema ou mudar temporização; não constitui correção
de vazamento ou erro de mapeamento. Artefato de análise em
`out/investigacao-fault-1a371/reproducao-demo/memoria-orcamento.md`.

O teste autorizado com 6080 MiB completou 600 segundos, saída 142 pelo
watchdog, sem falhas fatais registradas. Entretanto, não houve mensagens
st_gameflow() starting game: o log não demonstra cobertura da mesma transição
que falhou com 5056 MiB. A ausência de falha não confirma a hipótese de orçamento.
O jogo registrou Neo com 704 MiB de memória de depuração (6080 - 704 = 5376).
Isso sugere um limite não-debug de 5376 MiB para Neo; ainda é necessário
verificar esse caminho e o estado visual alcançado antes de alterar defaults.
Log e resumo: `out/investigacao-fault-1a371/demo-dmem-6080/`.
O usuário confirmou que a demonstração estava rodando nesse teste. Portanto,
a ausência dos marcadores st_gameflow não significa que o jogo tenha ficado
no menu. O resultado favorece investigar orçamento de memória, mas ainda
não comprova execução do mesmo caminho interno nem corrige eventual vazamento.

O teste seguinte com 5376 MiB completou 600 segundos pelo watchdog (saída
142), com 119 amostras até 596 segundos, sem falha fatal ou perda do dispositivo
Vulkan registrada. O jogo informou Neo, 5376 MiB totais e zero de memória de
depuração. As duas mensagens st_gameflow ocorreram (50.1868s e 00:01:58.72),
portanto essa execução cobriu os mesmos marcadores de transição que antecederam
a falha com 5056 MiB. Log e resumo em
`out/investigacao-fault-1a371/demo-dmem-5376/`.

O conjunto sustenta a hipótese de orçamento incoerente ao anunciar Neo com
o padrão de 5056 MiB do runtime: 5376 MiB é o limite não-debug sugerido pelo
próprio jogo. Ainda não prova ausência de vazamento nem identifica qual operação
esvaziou o bitmap. Recomendação: usar explicitamente 5376 MiB no launcher
dedicado PS4 Pro, mantendo o padrão genérico/base PS4 separado e documentando
a evidência e a limitação. Nenhum default foi alterado nesses testes.
