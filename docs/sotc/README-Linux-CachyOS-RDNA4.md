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
- 30 FPS estáveis observados com MangoHud.
- Redução de determinados artefatos de sombras em relação à versão anterior.

## Limitações conhecidas
- Artefatos gráficos residuais, especialmente nas sombras.
- Avisos Vulkan recorrentes e erros registrados pelo recompilador de shaders.
- Modo experimental de 60 FPS menos estável nos testes realizados.
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
env SOTC_EOP_DEFER=1 ./out/bb-probe /caminho/para/boot-linked.bin --app0 /caminho/para/CUSA08809 --content-profile /caminho/para/content.bin --timeout 0
```

O comando pressupõe que a preparação e a vinculação da imagem já foram realizadas. Essas etapas ainda precisam de documentação reproduzível para Linux.

### Áudio

O áudio foi testado com os módulos libSceNgs2.sprx e libSceUlt.sprx, obtidos legitimamente do firmware do próprio usuário.

### Arquivos proprietários

Este repositório não distribui arquivos do jogo, imagens vinculadas, dumps de firmware ou módulos proprietários da Sony.

### Monitoramento

O MangoHud foi utilizado para observar FPS e frametime. Os resultados descritos neste documento correspondem ao ambiente de teste informado acima.
