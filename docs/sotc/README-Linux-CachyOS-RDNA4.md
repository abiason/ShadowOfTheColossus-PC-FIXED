# Shadow of the Colossus — Linux / CachyOS / AMD RDNA4

Documentação experimental da adaptação Linux desenvolvida por abiason, baseada nos projetos de AjncSystem e xeodeo.

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
O script fixa os parâmetros acima; as demais variáveis e configurações existentes
continuam sendo herdadas. Não altera os padrões globais do projeto.

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

### Áudio

O áudio foi testado com os módulos libSceNgs2.sprx e libSceUlt.sprx, obtidos legitimamente do firmware do próprio usuário.

### Arquivos proprietários

Este repositório não distribui arquivos do jogo, imagens vinculadas, dumps de firmware ou módulos proprietários da Sony.

### Monitoramento

O MangoHud foi utilizado para observar FPS e frametime. Os resultados descritos neste documento correspondem ao ambiente de teste informado acima.
