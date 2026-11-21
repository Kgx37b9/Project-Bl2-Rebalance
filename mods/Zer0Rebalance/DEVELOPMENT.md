# Development

## Many Must Fall - causa principal: arrays nativos zerados (1.0.3, 2026-11-15)

SUPERSEDE as hipoteses de contexto de renovacao como causa da ausencia visual. A captura real19:39 local da1.0.2 mostrou configuration=False, apenas o no44 ZR_MMFWeaponGate entre os nos procurados (sem Delay/Deactivate originais) e51 outputs originais zerados, exceto o link substituido para44; os2 links novos ainda existiam. Isso explica a ausencia de efeitos visuais de Skill_Stealth e do encerramento nativo. A configuracao funcionava uma vez e a seguinte falhava porque o Delay_68 tinha sido apagado. Nao foi demonstrada interferencia de outro mod.

Causa na escrita: list(WrappedArray) guarda views dos registros. Substituir o mesmo array invalida/limpa seus registros antes de converter essas views, produzindo dados zerados. A copia do struct de sequencia nao torna independente cada view extraida depois. Agora TODAS as sequencias e linhas de EventData2, BehaviorData2, ConsolidatedOutputLinkData e ConsolidatedVariableLinkData sao copiadas individualmente antes das atribuicoes; KillEvents tambem recebe linhas independentes. Assinatura primitiva e referencias UObject sao capturadas antes de gravar; readback confere nos, subarrays, links, variaveis e eventos apos publicacao.

Removidos normalize_mmf_restealth, hook/endereco auxiliar e a mudanca de ContextObject da1.0.1/1.0.2: o grafo nativo estava apagado, logo a diferenca de contexto da captura anterior nao provava falha no contexto original. Preservados contexto nativo de renovacao, duracao/kill, delay nativo de encerramento sem kill e ramo original sem MMF. Nenhuma outra skill foi alterada.

16 testes aprovados:14 MMF e2 Precision adjacentes. Novo modelo de arrays invalida views antes de converter a atribuicao e reproduz os zeros quando nao ha copia independente. Regressoes conferem todos os nos originais, links nao alterados, variaveis/eventos, idempotencia, migracao, sequencia adicional e deteccao de writeback corrompido antes de ampliar KillEvents. Sintaxe/TOML conferidos. Fonte apenas; sem pacote/instalacao. Resultado visual/encerramento desta correcao ainda requer teste no motor apos FECHAR E REABRIR o jogo com fonte atualizado; a sessao corrompida nao deve ser reparada reconstruindo grafo parcial a quente.


## Many Must Fall - falha real da 1.0.1 e encerramento (1.0.2, 2026-11-15)

SUPERSEDE a conclusao de que o ajuste de contexto da 1.0.1 estava executando. Usuario confirmou ausencia de invisibilidade e encerramento incorreto sem kill. Log 19:32:07 local registrou AttributeError: Skill object has no attribute bDeleteMe. Skill e UObject, nao Actor; a guarda lancava excecao antes de alterar ContextObject. Removida a propriedade invalida e corrigido o fixture para NAO fornecer bDeleteMe, garantindo regressao realista. Validacao continua usando instigador, definicao, estado, pawn/mundo e autoridade.

Segundo problema estrutural: OnWeaponFired fornece SkillInstigator, mas nao Enemy. A rota antiga entrava no comparador do evento de dano melee sem esse alvo; nao havia garantia de chegar ao encerramento. O ramo MMF agora aponta diretamente ao Behavior_Delay_68 nativo de Skill_Stealth (0.5s), preservando suas variaveis e saida de desativacao. Ramo sem MMF, caminho de dano melee e grafo de kill/duracao nao foram alterados. Gate antigo migra sem duplicar nos; ausencia do delay aborta antes de remover filtro de kill. Nao ha timers Python nem varreduras adicionais.

17 testes focados/adjacentes aprovados: 15 MMF e 2 de Precision no mesmo evento nativo. Incluem Skill sem propriedades de Actor, contexto de renovacao, acao expirada, remoto/pausa/viagem, ramo sem MMF, delay/saida, migracao idempotente e asset ausente. Sintaxe/TOML conferidos. Correcao apenas no fonte; sem pacote/instalacao. Confirmar apos reinicio: kill de arma restaura invisibilidade; disparo sem kill encerra apos janela nativa; sem MMF mantem saida original. Log unico da normalizacao distingue se a guarda executou, sem afirmar resultado visual.


## Many Must Fall - contexto de invisibilidade (1.0.1, 2026-11-15)

Captura real 19:26 local: ativacao inicial de Skill_Stealth recebeu WillowPlayerPawn_1; apos kill, DeactivateSkill_149 removeu Stealth, ActivateSkill_206 ativou feedback e ActivateSkill_207 reativou Stealth apos 0.1s usando WillowPlayerController_5. Skill_Stealth voltou ao estado ativo e permaneceu assim, apesar da ausencia visual reportada. Portanto nao era simplesmente uma falha de extensao ou ausencia de chamada de reativacao.

Correcao: PRE restrito pelo endereco do ActivateSkill_207 normaliza apenas ContextObject para o pawn atual, como na ativacao inicial. Preserva SelfObject, EventData, KernelInfo, delay, grafo, ranks e bonus de tempo. Valida controlador local, autoridade, classe, mundo/pawn, vida e a instancia de Decepti0n ativa; nao reativa uma acao expirada. Outras ativacoes retornam antes de consultar o jogo. Sem varredura de skills, novo timer ou busca global. Reset/disable invalida a identidade de comportamento; nenhuma referencia a pawn e retida.

A captura comprova a diferenca de contexto; confirmar no motor se a normalizacao restaura a invisibilidade visual. Testes offline verificam guardas e argumentos, nao renderizacao. Reiniciar com o fonte atualizado antes de repetir kills de arma durante Decepti0n, parando de atirar apos cada kill.


## 1.0.0 ? preparacao para lancamento (2026-11-15)

Versao publica1.0; project/tool.sdkmod1.0.0; nome de menu Zer0 Rebalance. Pasta/projeto Python Zer0Rebalance preservados. README reestruturado para publicacao com tabela das15 skills, requisitos, instalacao, compatibilidade, creditos e licenca. Removidas notas antigas de etapa de desenvolvimento da apresentacao publica; historico0.x mantido no changelog. LICENSE.md preservado integralmente.

Esta etapa altera documentos/metadados e apenas a string de versao no log Python. Codigo de gameplay comparado por hash normalizado, AST e TOML validados; links locais e inventario dos seis arquivos conferidos. Nao repetir suites de gameplay para mudanca documental; os104 testes do passe anterior continuam sendo a evidencia offline, nao teste real da1.0. Nenhum pacote gerado/instalado.

Validacao no motor ainda pendente para correcoes recentes de Resurgence/MMF, ricochetes de Precision, disparos atrasados de At One with the Gun e bonus condicionais/troca de armas de Critical Ascensi0n. Coop continua sem validar. A designacao1.0 segue o pedido do autor; nao significa que esses testes nativos foram executados. Gameplay e pontos investidos nao foram modificados nesta preparacao.

## Precision: raio30m, mesma0.1.22 (2026-11-15)

## 2026-11-15 ? Zer0Rebalance0.2.4: retirada do experimento e auditoria

Removida integralmente a skill experimental de dura??o: defini??o, ?rvore, ?cone/pacote, configura??o, diagn?stico, integra??o de ranks e teste dedicado. A ?rvore volta ao conte?do nativo ap?s rein?cio completo; nenhuma migra??o/escrita de save. Removida a documenta??o do experimento abandonado.

Corre??es concretas: At One with the Gun usa EOpinionEnemy nativo (0), n?o Friendly2; o helper hipfire aposentado ? opcional para reconfigura??o. Cache de fonte limitado64 strings/bools e limpo no reset evita consultar _superfields novamente a cada tiro. Snapshot de Skills mant?m uma leitura/segundo e agora resolve path por defini??o uma ?nica vez: teste999 inst?ncias compartilha1 export de path, sem guardar atores/endere?os entre snapshots. Kill Confirmed trata controllerNone e world.bDeleteMe antes de ler tempo/estado. Unf0reseen restaura f?rmulas aninhadas em ordem inversa no cleanup/reset, incluindo frames com fatores diferentes.

Revisados loops, reentrada, weakrefs, limites de caches/registries e limpeza de viagem/disable. N?o foram introduzidos FindAll, scan global de atores, hook por tiro ou temporizador permanente. Valores de balanceamento preservados, incluindo decay2.5s de Critical Ascensi0n. N?o afirmar aus?ncia absoluta de falhas nativas ou ganho de FPS com base em revis?o est?tica.

104 testes afetados/adjacentes passaram: IronHand/cache compartilhado, AtOneWithGun, KillConfirmed, Unf0reseen, BeLikeWater/HUD/dano. Cobrem aliado2/inimigo0, helper descarregado, cache de hierarquia reusado/limitado/limpo, 999 inst?ncias com1 leitura por snapshot, estabilidade sem buscas/escritas repetidas, controlador/mundo inv?lidos e rollbackLIFO. AST/TOML v?lidos, fonte0.2.4; sem pacote/instala??o. Retestar no jogo troca de mapa/menu, ac?mulos e tiro empoderado; coop continua sem valida??o. Reiniciar completamente para descartar defini??es antigas em mem?ria.

## 0.2.2 ? Critical Ascensi0n e valores de Grim/Innervate

Autor confirmou gera??o de stacks com TODAS as armas. Path nativo ? CriticalAscention (grafia do asset). Link do BPD com LinkIdAndLinkedBehavior=-16777214 e ActivateDelay1 passa a5; atraso inicial6, demais links, cap999, misses e dura??o nativa dos stacks preservados. Removidas apenas restri??es SniperOnly/evaluator nativo IsSniper de main/stack, mantendo condi??o nativa OnFootOrRidingInBack para impedir pausa s? pela troca de categoria. EventoShotEnemy aceita fontes Bullet (inclui subclasses de armas) e Rocket, sem filtro elemental; grafo cr?tico nativo preservado.

Cada AID de b?nus do stack recebe initializer pr?prio: metade do AID original como Multiplier e Offset, Level ligado ao atributo nativo Weapon_Is_Sniper_Rifle, Power1. Resultado original*(0.5+0.5*IsSniper), inclusive upgrades de rank, sem substituir valores por constantes ou somar COM manualmente. Contexto/update de modifiers continua nativo; nenhuma rotina Python por tiro/stack ou tick novo. O teste de f?rmula n?o comprova a atualiza??o real do modifier ap?s troca de arma: validar isso no jogo.

Grim0.10/rank e Innervate gun damage0.04/rank; regen0.016/rank e movimento preservados.18 testes focados passaram: cinco Ascension e treze Grim/Innervate, incluindo f?rmula sniper/n?o-sniper, ranks, fontes, constraints, atraso inicial preservado, idempot?ncia e assets ausentes. AST/TOML/vers?o0.2.2 conferidos. Sem pacote/instala??o; testar ganho de stacks com sniper/pistola, b?nus ao alternar armas e perda entre stacks5s ap?s a car?ncia nativa.

## 0.2.1 ? cr?ticos reais e encerramento por disparo

Captura16:38local: cinco cr?ticos no AdjustDamage, Resurgence ativa5/5, contexto v?lido e escudo vazio/parcial; zero chamadas IncrementPlayerCriticalHitStat. Decepti0n/MMF ativos16:39:20, ausentes na kill de arma seguinte. Dados nativos mostram Skill_Stealth.OnWeaponFired indo diretamente a DeactivateSkill_42 (Decepti0n); o evento de dano melee segue compara??es e Delay_68, cuja dura??o nativa ?0.5s. Ampliar somente KillEvents n?o corrige a sa?da por disparo.

Resurgence: novo POST normal de AdjustDamage verifica instigador local, bWasCrit e dano positivo ao escudo/vida; chama o helper de recupera??o existente (identidade, contexto recente, FFYL, maxshield e reentrada preservados). O hook de estat?sticas foi removido da lista. Sem consulta peri?dica ou cooldown novo.

MMF: grafo de Skill_Stealth recebe um Behavior_Conditional privado que usa o avaliador nativo de MMF em ESS_Running (Conditional_121 de Skill_Deception). Output1 segue a entrada do caminho melee, Output2 mant?m a sa?da original por disparo. O output SkillInstigator do evento alimenta os dois contextos, sem fabricar Enemy; copiadas as subarrays/estruturas nativas, sem mudar delays/tabelas de dura??o. Mesma fonte de kill sem restri??o e despacho original preservados. Modifica??o est?tica/idempotente, sem hook/timer por tiro e sem reativar a??o j? expirada. A janela preservada ? a nativa; isto n?o promete renovar uma a??o cuja janela j? terminou antes de um proj?til lento matar.

62 testes focados/adjacentes (Resurgence, MMF e Precision) aprovados; incluem cr?tico real sem stats, n?o cr?tico/danozero/alheio, COM, grafo true/false, contextos corretos, idempot?ncia e falta de asset sem altera??o parcial do filtro de kill. AST/TOML v?lidos. Fonte0.2.1, sem pacote/instala??o. Validar ap?s rein?cio cr?ticos com escudo vazio e kills de pistola/sniper durante Decepti0n; comparar a??o sem MMF e melee. O resultado nativo ainda ? pendente.

## 0.2.0 ? Grim, Pin point e Innervate

Grim cooldown rate0.08/rank. Optics mant?m path/identificadores internos para COM e passa SkillName="Pin point", accuracy WeaponSpread-0.20/rank; recoil/ADS preservados. Innervate usa0.016 tanto na apresenta??o quanto no multiplicador de HealthMaxValue da cura/s; dano0.03 e movimento inalterados.18 testes focados das tr?s skills passaram, incluindo ranks COM e cache. AST/TOML v?lidos, README/menu/vers?o atualizados. Sem pacote/instala??o ou altera??o de outras mec?nicas.

## Precision0.1.28 ? publicar ReflectionData ap?s cr?tico confirmado

Captura14:37local comprovou chance1.0 no Reflect e no POST de TakeDamage, por?m ReflectionData permaneceu REFLT_None at? o fim. Isso refuta a hip?tese de que manter somente os modifiers ap?s o retorno faria o motor recalcular o resultado do mesmo impacto. Os testes anteriores validavam aplica??o/remo??o de atributos, n?o emiss?o da decis?o nativa.

Headers Engine/WillowGame confirmam DamageSummary.ReflectionData (ReflectionType, ReflectedDamageScale, ReflectedDamageToReflector, bReflectTowardAttacker, ReflectedInaccuracyModifier, bReflectProjectiles) e EReflectionType.REFLT_Instigator. Agora o evento exige bWasCrit real no summary, copia o resultado mantendo dano/escudo/eventos originais e preenche reflex?o do instigador, escala0.5+0.1*rank, sem redirecionar ao atacante nem for?ar reflex?o de proj?teis f?sicos. Resultado j? diferente deNone ? preservado. Revalida owner/pawn ap?s callbacks antes da escrita. N?o chamar TakeDamage novamente, n?o reaplicar b?nus do acerto original e n?o escrever SetCanReflect/bActorReflected.

Pulsos de atributos/raio e cleanup existentes permanecem nesta vers?o; scopes aninhados n?o rearmam. A execu??o nativa posterior, inclusive pol?tica dos proj?teis j? refletidos, ainda precisa ser validada no jogo: n?o alegar que os testes Python provam aus?ncia de toda cadeia no motor. Log de publica??o apenas uma vez por sess?o, sem spam por hit.40 testes Precision aprovados, agora incluindo decis?o nativa, dano original preservado, rank, n?o cr?tico e reflex?o externa existente. AST/TOML v?lidos; vers?o0.1.28 sem pacote/instala??o. Pr?ximo teste real: v?rios cr?ticos perto de outro inimigo, procurar reflex?o/dano secund?rio e linha de resultado publicado; se falhar, capturar ReflectionData no retorno usando o probe existente.

## Precision0.1.27 ? bloqueio comprovado e dura??o do pulso revisada

Capturas reais14:23 e14:26 locais mostraram eventos cr?ticos chegando ao Reflect com contexto v?lido e inimigos pr?ximos, por?m bCanReflectFalse e chance0. A segunda confirmou sniper, ReflectionData.REFLT_None e scopes zerados ao fim: n?o h? evid?ncia de latch permanente ou recurs?o presa. O campo transit?rio foi usado indevidamente como pr?-condi??o obrigat?ria do b?nus; a guarda foi removida sem escrever SetCanReflect, bActorReflected ou ReflectionData.

Revisado tamb?m o lifetime: o POST de TakeDamage roda antes de retornar ao chamador que processa o disparo. O frame armado sai da pilha, mas passa a pending, mantendo modifiers/raio at? o pr?ximo impacto (mesmo n?o cr?tico/de outro instigador) ou tick do controlador local. Limpar pending antes de callbacks; n?o permitir novo pulso em dano aninhado enquanto o original est? ativo. Cleanup de viagem/disable inclui pending; reset apenas esquece refer?ncias de mundos antigos. Sem timers extras ou busca peri?dica de atores. O efeito exato desse lifetime sobre a reflex?o nativa requer novo teste real.

36 testes Precision aprovados com bCanReflectFalse nativo preservado, visibilidade do b?nus ap?s POST, cleanup no pr?ximo hit/tick, controlador alheio, disable, cinco ativa??es e falha seguida de sucesso.37 testes adjacentes de Be Like Water aprovados por compartilhar manuten??o. AST/TOML conferidos, vers?o0.1.27; sem pacote/instala??o. Validar ap?s rein?cio v?rios cr?ticos com pistola/sniper perto de outros inimigos, depois tiros n?o cr?ticos, sem supor sucesso nativo a partir de mocks.

## Unf0reseen0.1.26 ? mesmo raio para dano e atra??o

RadiusFormula da explos?o agora usa UNFORSEEN_PULL_RADIUS (2000unidades/20m), com constante fixa, scale1 e sem atributos/initializer de raio. A atra??o e explos?o compartilham a mesma refer?ncia de configura??o; n?o foi adicionado hook/scan. Mantidos f?rmulas de dano/DoT, falloff, restri??es nativas e marca ap?s dano positivo.18 testes focados aprovados, incluindo igualdade dos raios ap?s execu??o e restaura??o dos scopes. AST/TOML v?lidos; confirma??o visual no jogo pendente. Sem pacote ou instala??o.

## Precision0.1.25 ? raio inteiro e reativa??o por impacto

Log real de 15/11/2026 ?s 12:59:56 local: `Could not validate Precision reflection: Unable to cast Python instance of type float to C++ type int`. Header WillowGame confirma `int BulletReflectionRadius`. A mudan?a para30m declarou3000. e convertia o raio anterior parafloat; isso fazia a escrita de ativa??o falhar e tamb?m poderia tornar inv?lida uma restaura??o ap?s altera??o efetiva. O logger deduplica esse erro, portanto aus?ncia de linhas repetidas n?o prova aus?ncia de novas falhas.

Constante3000 e snapshot anteriorint, mantendo a escrita tempor?ria e restaura??o condicional por impacto. N?o adicionado timer, busca global ou estado persistente para rearmar. Fixture nativa agora rejeita escritafloat: cinco cr?ticos consecutivos ativam/limpam os dois modifiers e restauram o raio, e uma falha simulada n?o bloqueia o cr?tico seguinte.32 testes focados passaram, preservando fronteira30m, COM, filtros, recurs?o e cleanup. A falha de convers?o est? comprovada; a hip?tese de um bloqueio permanente separado n?o foi confirmada. Validar v?rios cr?ticos em inimigos pr?ximos ap?s atualizar/reiniciar.

## Be Like Water 0.1.24 ? configura??o independente dos objetos aposentados

A captura WaterProbe de 15/11/2026 ?s 12:54 (local) mostrou a skill nativa ativa em 5/5 e CurrentPawnSpeed variando entre zero e movimento, mas `_water_configured=False`, contexto/estado/HUD ausentes. Isso localiza a falha antes da gera??o de ac?mulos; a captura n?o comprova rejei??o da habilidade auxiliar de movimento pelo gerenciador.

A configura??o ainda exigia ambos os antigos BeLikeWater_Melee_Active/Ranged_Active, embora o novo efeito removesse suas refer?ncias no grafo e TrackedActiveSkills. Esses objetos n?o s?o necess?rios e podem deixar de estar carregados. Sua aus?ncia agora ? tolerada, com limpeza somente se existirem e fallback do ?cone de dano para o ?cone principal. A causa espec?fica do descarregamento n?o foi medida pela captura; a regress?o reproduz a depend?ncia incorreta e valida reconfigura??o, movimento e HUD sem os objetos antigos.

Corrigido tamb?m o filtro do dano parado: EOpinion.OPINION_Enemy resolvido na configura??o, em vez do literal2 (Friendly). Mock antigo com inimigo2 mascarava a falha. Trinta e sete testes de movimento, transi??o, COM, HUD sem sobreposi??o, dano por fonte, scopes e cleanup passaram. N?o foram alterados valores/timing ou outras habilidades; sem pacote ou instala??o. Validar ap?s rein?cio: mover por tr?s segundos, observar cinco ac?mulos/b?nus; parar e observar transi??o para os ac?mulos de dano; repetir ap?s viagem.

PRECISION_RICOCHET_RADIUS=3000 unidades, seguindo100unidades/m usados no projeto. Preflight de alvos passa a usar esse valor ao redor do ponto atingido. Não basta ampliar a lista Python: o motor continuava com BulletReflectionRadius1800. O frame agora ajusta temporariamente esse campo do GlobalsDef do pipeline para3000 e o restaura no mesmo cleanup do pulso. Guarda referência fraca e valor anterior, registra antes do setter, restaura após falha parcial e não sobrescreve mudança externa cujo valor já difira do aplicado. Sem alteração permanente no GlobalsDef nem novos timers/scans. Dano e demais skills preservados; metadados mantêm0.1.22.30 testes focados passaram, incluindo fronteira3000/3000.01, raio nativo durante o hit, restauração e mudança externa. Confirmar distância efetiva no jogo.

## Unf0reseen0.1.23: chamadas nativas por nome (2026-11-15)

Erro registrado na sessão0.1.22: Could not prepare Unf0reseen explosion, conversão UObject->WrappedStruct. A preparação passava objetos e structs por posição em GetBehaviorContext; a chamada seguinte de ApplyBehaviorToContext da atração também era posicional. Headers nativos confirmam os nomes SelfObject/MyInstigatorObject/OtherEventParticipantObject/ContextData/EventData e ContextObject/SelfObject/MyInstigatorObject/OtherEventParticipantObject/EventData/KernelInfo, respectivamente. Ambas agora vinculam os parâmetros por nome, evitando depender da ordem refletida do SDK. ContextData usa uma cópia de TargetContext; EventData/KernelInfo vêm dos argumentos nativos existentes. Retorno com out-parameters continua usando o primeiro elemento como contexto retornado.

Correção adjacente: Death Mark descartava hostis ao comparar opinião com2. A configuração de Unf0reseen agora resolve EOpinion.OPINION_Enemy uma vez, e o pós-dano usa o valor nativo0. Fixtures também foram corrigidas para inimigo0/neutro1/amigo2. Não houve mudança de coeficientes de dano/DoT, raio/momento de atração ou duração da marca, nem alteração de Precision ou outras skills.

18 testes focados passaram: contratos keyword-only, tipos/identidades dos objetos e structs, ordem atração->dano, escala por nível, duas fórmulas restauradas, alvos hostis/neutros/amigos, ponto de Death Mark, falhas parciais, contexto inválido, viagem e recursão. AST/TOML e versão0.1.23 em metadados/README/log verificados. Nenhum pacote gerado/instalado. Confirmar no jogo: Decepti0n com Unf0reseen e Death Mark alocadas, clone explodindo perto de inimigos vivos, atração/dano/marca e ausência do erro de preparação no log.

## Precision0.1.22: pulso direto nos atributos do pawn (2026-11-15)

Log real da0.1.21 registrou retornoFalse de ActivateSkill. Consulta seguinte confirmou SkillClass=WillowGame.Skill no parent/helper, restrições on-foot equivalentes, lifetime correto e definição emcache igual à real. A causa interna da recusa não foi comprovada. Headers ASkillEffectManager documentam bAllowSkillActivation e filas de ativação, mas não se deve afirmar que esse flag estava falso sem captura.

Removida a dependência de criar uma skill auxiliar durante o callback. Dois AttributeModifiers próprios MT_PostAdd são criados uma vez sob Precision com KEEP_ALIVE: chance+1 e delta de dano(.1*GradeEfetivo-.5), aplicados por Pawn.AddModifier. Os campos BulletReflectionOffEnemyChance/BulletReflectedOffEnemyDamageScale e suas ModifierStack/BaseValue existem nos headers de WillowPawn. O grafo continua apenas como origem do evento crítico e sua ativação original é bloqueada; o helper legado não precisa ter instância ativa.

Frame guarda WeakPointers de pawn/mundo e a lista exata dos modificadores adicionados. Registrar cada entrada antes do AddModifier permite rollback se a chamada aplicar parcialmente e lançar erro. Cleanup remove somente essas instâncias em ordem reversa; abandonado o mundo antigo, não escrever em ator de outra instância. Aninhar impactos com pulso armado continua bloqueando um segundo pulso. Não alterar valores-base nem zerar stacks de outros mods; não há ActivateSkill/DeactivateSkill ou lookup de assets no caminho crítico. Timing permanece o mesmo, sem supor que ele explique a recusa anterior.

28 testes focados passaram: manager indisponível não impede pulso, chance0->1->0, Grade1/5/10/11, valores preexistentes, rollback parcial, fim do escopo, recursão e troca de mundo. Probe informa pulse_mode=pawn_modifiers e não trata ausência do helper como falha nesse modo. Metadados/log/README0.1.22 e AST/TOML conferidos. Falta confirmar aumento real da chance e ricochete após atualizar/reiniciar; nenhum pacote gerado/instalado.

## Precision0.1.21: ativação explícita do pulso (2026-11-15)

Captura14:42:22UTC em0.1.20: guards liberadas e armed=True, porém após Behavior_ActivateSkill POST a definição do helper existia e IsSkillActive=False/IsSkillPaused=False; nenhuma instância correspondente em ActiveSkills, chance de reflexão0. Não foi demonstrada a razão interna de a ativação via behavior falhar. Isso diferencia a falha de um efeito simplesmente pausado, de um Grade incorreto observado ou de cleanup precoce comprovado.

guard_precision_reflection agora chama SkillManager.ActivateSkill(controller, helper, None, 1) explicitamente depois das guardas, como os helpers já gerenciados pelo módulo. Reivindica o frame antes do callback, bloqueia a chamada original do behavior para impedir duplicação e não reutiliza snapshots nativos após o callback. Rejeição explícita gera log limitado e mantém cleanup pareado para alterações parciais. bUpdatingSkills impede ativação naquele momento. Apenas a definição própria com KEEP_ALIVE é armazenada; ativação e cleanup deixam de procurar o asset por hit. Escopo TakeDamage, seleção nativa, dano e COM preservados; não foi alterado o timing por hipótese.

26 testes focados passaram, incluindo chamada com Grade1, simulação de chance0->1->0, repetição do mesmo evento, recusa/cleanup, manager ocupado e ausência de lookups por hit. Simulação não comprova chance ou ricochete no motor. Probe temporário observa agora POST_UNCONDITIONAL do behavior, pois a chamada original será bloqueada mesmo quando a ativação explícita for aceita. Metadados/log/README em0.1.21; AST/TOML conferidos, nenhum pacote gerado/instalado.

## Precision0.1.20: remover veto de trajetória adicional (2026-11-15)

Captura da0.1.19 às14:34:54UTC mostrou críticos/bCanReflect válidos, Grade5 e inimigos hostis vivos a602.56/778.90/1602.14/1715.24 unidades dentro do raio1800. Todas as chamadas extras FastTrace retornaramFalse, target_cache ficou negativo e Reflect não ativou o helper. Isso confirma a pré-checagem como bloqueio atual, mas não demonstra por que FastTrace falha nesse cenário nem valida todos esses destinos para a seleção nativa.

_precision_has_target agora faz somente preflight limitado de hostilidade nativa, mundo, distância e vida; não veta a habilidade por FastTrace adicional. A escolha definitiva continua pertencendo ao mecanismo nativo de reflexão. Não foi implementado dano direto por Python, não se forçou uma vítima através de paredes, não se alteraram raio/dano nem a política bCanReflect. Sem inimigo próximo o código continua bloqueando e não arma helper. Comparação com o traço antigo permanece apenas no diagnóstico temporário, identificada como legacy_extra_trace.

22 testes focados aprovados, incluindo traço extra falso com alvo válido, ausência de alvos, inimigos inválidos, enum, Grade/COM, escopos/recursão e cleanup. Metadados/README/log em0.1.20; AST/TOML validados. Confirmação nativa de ricochete após esta correção pendente; nenhum pacote gerado/instalado.

## Precision: evento critico depois de AdjustDamage - 0.1.18, 2026-11-14

Captura nativa22:57:40..22:58:10UTC confirmouconfiguredTrue/rank5/contexto correto,10AdjustDamage e4Reset/4Reflect. Toda chamadaReflect chegoucomframes0 earmedNone; portanto guard bloqueava apesar de grafo/evento critico disparar. Alguns AdjustDamagePRE tinham bCanReflectFalse, outrosTrue; nao usar campo antes da inicializacao como elegibilidade definitiva. Nao supor que DamageEvents ocorrem dentro deAdjustDamage.

Scope agora abre emWillowAIPawn/WillowPawn.TakeDamagePRE e fechaemPOST_UNCONDITIONAL. AdjustDamagePRE apenas vincula Pipeline/HitLocation ao frame correspondente (mesmoInstigator/vitima); guard continua exigindo bCanReflect valido durante evento, grade, contexto, alvo secundario eFastTrace. Chamadas da classe-base usam alias do mesmoframe; somente ultimoPOST retira helper. Hits aninhados com pulso armado nao ativam outra reflexao; semTimer ou busca de atores porTick.18 testesPrecision aprovados incluindoevento aposAdjust, flag inicialfalse/depoistrue, superclassalias, pipelineestrangeiro e ausencia de frameouter. Probe somenteleitura30s pode verificar pulso nosPOST deActivate apos atualizar/reiniciar. Balanceamento intocado; gameplay da correcao ainda pendente.

## Precision: tipo nativo de link e descricao - 0.1.17, 2026-11-14

Log22:42:08UTC: Could not configure Precision, cast WrappedStruct->WrappedArray. Headers nativos confirmam BehaviorVariableLinkData (legado) tem LinkedVariables TArray<int>; BehaviorVariableLinkData2 tem LinkedVariables SubarrayData e campos VariableLinkType/ConnectionIndex de8bits. BehaviorSequenceData.ConsolidatedVariableLinkData usa array deLinkData2. _precision_graph estava construindo o tipo legado comSubarrayData, portanto falhava antes de atualizarSkillDescription. Corrigido somente tipo paraData2, sem alterar grafo/valores. Teste restritivo rejeita tipo legado, exige8linksData2; outro restaura descricao antigaAccuracy paraCriticalHits/ricochet e footerRicochetDamage, sem trocar efeitos.13 testesPrecision aprovados; AST/TOML conferidos. Aguardando motor apos atualizar/reiniciar; sem pacote/instalacao.

## Atributos ausentes, sinais e HUD - 0.1.16, 2026-11-14

Captura nativa ZeroAssets19:56/20:01UTC confirmou Optics/Precision/Water configuradasFalse. Definicoes, layouts e apresentacoes eram nativos; PlayerZoomTimeModifier e BulletReflectionOffEnemyChance estavam ausentes, enquanto SkillGradeModifiers.Precision e WillowDmgSource_Bullet estavam presentes. LoadPackage D_Attributes executado pelo usuario nao disponibilizou os atributos nem alterou flags. Nao presumir que um objeto no dump existe na sessao. Console corta linhas longas (~255caracteres); usar runpy com arquivo de leitura e comando autocontido, sem depender de variaveis criadas em comandos que falharam.

Solucao propria: _property_attribute constroi AttributeDefinition e resolvers privados KEEP_ALIVE com contexto/propriedade verificados nos dados nativos: Pawn/ZoomTimeModifier, Pawn/BulletReflectionOffEnemyChance, Pawn/GroundSpeed, Controller/ReceivedBulletDamageModifier. CachedPropertyNone para resolver por tipo em runtime. Optics/Water aceitam caminhos nativos e privados conhecidos para idempotencia/migracao; Precision preserva grafo/rank/failsafes. Sem carga repetida de pacote nem busca global. Logs unicos confirmam configuracao concluida, sem confundir isso com verificacao do efeito no motor. Iron Hand passa SignStyle=SIGNSTYLE_Positive/bDisplayAsInverseFalse (enum EAttributeValueSignStyle), mantendo valor real-.05/rank e vida intactos. Optics usa o mesmo estilo positivo explicitamente.

Be Like Water: dois SkillDefinition de feedback sem efeitos/constraints/eventos, infinitos e rastreados, com CustomStackCount->Skill.Grade1..5, separados do rank efetivo do gameplay. Movimento usa iconeFluidity; dano usa Fluidity-Gun do antigo Melee_Active. Parent e helper antigo nao sao alterados para simular contadores: ambos antigos dividiam slot4. Alocador reserva logicos/remapeados, arvore de skills compradas, filhos inativos e icones fisicos; limita grafo512 e capacidade nativa11. HUD cheio nao remove buffs. AddTrackedSkill/Activate/Deactivate/UpdateGrade/UpdateSkillIcons interrompem o passe; resolver novamente apos callbacks, especialmente antes de atualizar HUD apos hide. Reconciliar alteracoes de counts e verificar integridade estavel1s; limitar recusas/erros1s e evitar escritas quando valores nao mudaram. Reusar tick existente sem novo hook de frame/scan de atores. Morte/respec/viagem/reset limpam ou invalidam contadores. Somente definicoes privadas estaticas ficam em cache.

53 testes focados/adjacentes aprovados: Optics/Precision, Water movimento/dano,13HUD, Iron Hand apresentacao e2caches adjacentes. Cobertos atributos ausentes, COM, dois contadores, slots inativos/ocupados, HUD cheio, menu, limpeza, callback com troca de mundo e throttling. AST/TOML/versoes conferidos. Sem build/instalacao. Testar apos reinicio: descricoes atualizadas, velocidades de mira/recoil, ricochetes criticos com/sem alvo secundario e dois contadores durante transicoes. Os mocks nao provam a ordem de reflexao nativa nem resultado visual do Flash.

## Unf0reseen - 0.1.15, 2026-11-14

Nome real do asset: GD_Assassin_Skills.Cunning.Unforseen (sem segundo e). O dano nativo nao vem diretamente do BPD dessa passiva: e Behavior_CauseDamage_0 em GD_Assassin_Skills.ActionSkill.Skill_Stealth:BehaviorProviderDefinition_0, node8, Context=Player e TargetContext=clone (variavel1). DamageFormula e StatusEffectDamage sao alimentados por variaveis do grafo. Behavior_Explode_0 no node10 fornece FX, com DamageFormula0; nao aplicar dano duas vezes nem reconstruir a arvore opaca para alterar a explosao.

No PRE do leaf exato, ler os inputs ja resolvidos pelo kernel e multiplicar apenas BaseValueScaleConstant por 1.25 + clamp(stage-1,0,89)*1.5/89. Manter BVC/atributo/initializer: multiplicar BVC e BVSC ao mesmo tempo duplicaria o fator no termo constante. Rank/COM e escalador global ja estao no input nativo; nao acrescentar rank ou uma potencia de1.05 novamente. POST_UNCONDITIONAL restaura somente os campos que ainda correspondem a escrita propria, preservando outras alteracoes. Reentrada de um input ainda igual ao do parent usa sua base nao multiplicada; profundidade limitada8.

Converge real e Behavior_CauseDamage_12 de Phaselock: Radius2000/Momentum-110000/Damage0. Clone privado de nosso proprio leaf usa esses valores confirmados nos dados do jogo, sem depender de carregar assets da Maya, sem teleporte e sem PawnList. GetBehaviorContext resolve o TargetContext real; copiar os contextos resolvidos para o leaf privado somente durante sua chamada, limpar ContextObject/SelfActor ao terminar. Pull zero e sem status, aliados ou dano proprio. O impulso e iniciado antes do dano; nao foi adicionado um atraso de simulacao para esperar que todos cheguem ao centro. Raio de dano original512 preservado. Deslocamento efetivo e imunidades nativas dependem do teste no motor.

TookDamageFromEnemy durante o leaf aceita somente DamageCauser com endereco do leaf original, instigador local e dano final positivo de vida/escudo. Nao aceitar mero estar no raio, puxao de dano0, DoT posterior ou outro causer. Colecao deduplicada por endereco, WeakPointer, limite128 por explosao. Depois de o dano original completar, alvos vivos/inimigos recebem via seu Controller Behavior_DeactivateSkill/Behavior_ActivateSkill a definicao nativa DeathMark_Marked (8s). Remover marca anterior evita empilhar copias; revalidar alocacao/contexto depois do callback de remocao. A marca nao amplifica retroativamente o primeiro dano da explosao. Logs de preparo, primeiro hit reconhecido e pedido de ativacao sao limitados; pedido de ativacao nao e prova de modificadores aplicados.

18 testes focados/adjacentes aprovados:15 novos mais cache estavel, invalidacao de snapshot e dano aninhado de Water. AST/TOML/versionamento conferidos; sem pacote gerado ou instalado. No jogo: reiniciar, usar Decepti0n entre inimigos proximos e ao redor do raio original de dano; confirmar puxao, dano e marca com/sem Death Mark, COM e global scaler. Conferir especialmente o formato real retornado por GetBehaviorContext e se o DamageCauser do hit e o behavior esperado. Se esses contratos divergirem, coletar probe curto; mocks nao comprovam esse despacho nativo. Co-op/autoridade de clientes ainda nao validados.

## Be Like Water - dano generico, 0.1.14, 2026-11-14

Usuario confirmou todo o dano (armas/melee/granadas/status), mantendo condicao dos stacks, sem exigir alvo de costas/desatento. Dump Ambush usa PlayerAttackUnsuspectingTargetModifier; esse atributo e condicionado no pipeline e nao pode substituir diretamente o Amp sem introduzir outra condicao. Implementado multiplicador generico por fonte no coeficiente atual Received{Bullet,Grenade,Melee,Rocket,StatusEffect,Skill}DamageModifier do destinatario, somente durante o AdjustDamage proprio. Delta MT_PostAdd = valor_atual * .02 * Grade_efetivo * stacks. Preserva modificadores existentes e imunidade (coeficiente<=0), sem tocar em Ambush, dano-base da arma ou repetir TakeDamage. Nao declarar que a categoria matematica interna e aditiva ao atributo condicionado de Ambush: este ajuste implementa o multiplicador generico solicitado com a condicao de stacks existente.

Retirados begin/finish_water_shot, cache de Amp da arma e integracao de base compartilhada no tiro de At One. _remove_shot_amp continua exclusivamente como limpeza do Amp de At One. Mantidos movimento, temporizacao, decaimento e grade COM. Helpers privados de atributos usam contexto de Controller e resolver privado validado, com CachedProperty=None. Pool estatico de modificadores por profundidade/fonte, no maximo8 scopes; cache de classificacao64 e busca de ancestrais limitada16. Nenhuma busca em ActiveSkills por impacto; nenhum novo driver periodico.

PRE suspende bonus do parent em hits aninhados no mesmo destinatario; hits de outro atacante nao herdam bonus e POST_UNCONDITIONAL restaura parent/retira o atual. Viagem/disable limpam escopos com referencias fracas; Destroyed invalida sem tocar no mundo antigo. Validacao focada:12 testes de dano generico +8 de movimento/decay e2 integracoes de At One, total22; confirmar dano real de armas/melee/granadas/DoT no jogo apos reinicio. Historico Amp nas secoes anteriores e obsoleto para Be Like Water, preservado como registro de desenvolvimento.

## At One with the Gun - 0.1.13, 2026-11-14

Dump nativo: parent tem 3 efeitos de apresentacao de hipfire, reload por DesignerAttribute e magazine MT_PostAdd+1/rank, condicionado a SniperRifleOnly. BPD9 ativa child IsNotIronsighting que aplica os tres bonus reais de hipfire. Remover o grafo e os efeitos do child, manter exatamente reload/magazine e constraint do parent. Runtime le Grade efetivo mesmo com parent pausado ao usar outra categoria; assim o novo efeito funciona com qualquer arma sem estender os passivos de sniper a todas as armas. Rodape reaproveita apresentacoes reload/magazine e troca a antiga de accuracy por Amp .20/rank TARGET_None.

Wrappers Fire/Shared/Extra compartilham token consumivel. InitStats associa projeteis fisicos ao token durante emissao; POST normal confirma tiro e POST_UNCONDITIONAL retira modificador/descarta token de chamada cancelada. TookDamageFromEnemy ja observado no motor em pesquisa Ranger recebe causer/pipeline: aceitar apenas dano positivo de bala/foguete contra inimigo com registro valido. Token contado e marcado antes de incrementar stack; pellets subsequentes retornam antes das leituras de skill. Aos10 preparar proximo disparo; consumo confirmado troca ciclo e zera stacks, impedindo projeteis atrasados do ciclo anterior semearem novo preparo. Sem contador temporal para stacks. Registro da arma limitado16 e projeteis512, referencias fracas; janela de associacao30s nao e duracao dos stacks.

Limitacao conhecida herdada do caminho nativo observado: quando DamageCauser e arma e nao ha identidade especifica do projetil, o fallback usa o grupo MAIS RECENTE daquela arma. Mocks nao comprovam separacao perfeita entre tiros leves atrasados sobrepostos; nao prometer esse caso antes do teste no motor. Projeteis fisicos registrados preservam identidade exata. Rotas desconhecidas falham sem conceder stack. Validar especialmente shotgun, Sand Hawk/lentos, ricochete e lancadores; capturar eventos reais se houver divergencia, nao substituir identidade por ICD.

Amp e MT_PostAdd absoluto: InstantHitDamage base *.20*rank, removido no POST incondicional. One e Be Like Water compartilham base do primeiro escopo aberto, evitando multiplicacao acidental e garantindo resultado independente da ordem dos hooks. Limpeza PRE travel/disable remove modificadores com atores validos; Destroyed esquece frames sem acessar mundo antigo. Cache de grade existente inclui parent/child; nenhum polling novo. Logs de preparo e Amp verificado apenas na primeira ocorrencia. 16 testes novos e4 integracoes adjacentes aprovados; sintaxe/TOML conferidos. Sem pacote gerado/instalado; validacao no jogo pendente.

## Innervate - 0.1.12, 2026-11-14

Dump nativo confirma quatro efeitos: FootSpeed .07; HealthActiveRegenerationRate TARGET_None .008 (apresentacao); HealthPassiveRegenerationRate TARGET_Self MT_PostAdd com HealthMaxValue como atributo e escala .008; WeaponDamage .02. Ajustar dano para .03 e os DOIS coeficientes de cura para .01, tanto base quanto upgrade. Manter HealthMaxValue na cura real, sem transformar percentual em valor absoluto. Reutilizados apresentacoes, condicao Decepti0n, HUD8 e refresh compartilhado com Grade efetivo; nenhum hook/polling extra. Seis testes focados/adjacentes aprovados; confirmar valores e cura no jogo apos reiniciar. Nao gerado pacote.

## Precision - 0.1.11, 2026-11-14

Investigacao primaria nos dumps nativos de The Nth Degree e Critical Ascension, headers do jogo e stubs do SDK. Nth Degree ativa BulletReflectionOffEnemyChance; nao foi importado nenhum asset ou grafo de Gaige. Precision usa um grafo privado minimo que limpa o pulso anterior, recebe bWasCrit do evento nativo de dano de bala e ativa o helper somente no ramo verdadeiro. Atributo privado resolve BulletReflectedOffEnemyDamageScale; initializer usa o grade nativo de Precision uma unica vez: delta = 0.1 * rank - 0.5, somado a base nativa 1. Assim rank1=0.6, rank5=1 e rank11=1.6. RoundingMode deve ser Float.

Escopo PRE/POST_UNCONDITIONAL de AdjustDamage; guard na ativacao do helper exige contexto local valido, autoridade, skill ativa, bCanReflect e outro inimigo vivo no raio nativo com FastTrace livre. Busca limitada a 256 pawns, cache por alvo de 0.1s e no maximo 64 entradas; WeakPointer para atores. Sem alvo, contexto vencido, pausa ou reentrada, bloquear apenas a ativacao privada. O POST remove o pulso; viagem/disable limpam e invalidam frames. Disable tambem retira DamageEvents para nao deixar o grafo executar sem guard.

Limite de evidencia: mocks validam configuracao, calculo e protecoes, mas NAO provam a ordem entre DamageEvents e reflexao dentro do motor. Testar depois de reiniciar: critico com dois inimigos proximos deve ricochetear; tiro comum e inimigo isolado nao; repetir com shotgun e COM acima de 5. Conferir log antes de ampliar a implementacao. Nenhum pacote gerado/instalado nesta etapa.

## 0.1.4 - Kill Confirmed

Dump nativo: grafo13 ganha stacks por links atrasados .5s e limpa cinco instancias imediatamente ao sair da mira. Substituido somente esse controlador temporal: .25s para ganhar, 2s para perder um. Aiming por WillowPlayerController.IsZoomed confirmado no header. Manter helper nativo KillConfirmed_Stack e initializer de Grade, HUD e limite5. Cache de rank/contagem usa snapshot compartilhado; verificacao local limitada, sem scans por tick. Escritas ActivateSkill/DeactivateSkill apenas na mudanca de contagem; abandonar tick apos callbacks. Rezoom reinicia prazo, viagem/disable esquecem contexto. Reiniciar apos instalar.

11 testes focados aprovados; motor pendente. Testar cinco stacks em aproximadamente1.25s, perder um a cada2s ao sair da mira e voltar a mirar antes do proximo decaimento.

# Desenvolvimento — Zer0 Rebalance

## Fearless — 0.1.2, 2026-11-13

Alterado somente o subavaliador nativo AttributeExpressionEvaluator_22 da condição privada de Fearless: antes CurrentShield<1, agora CurrentShield>=MaxShield×.999999. Tolerância mínima evita oscilações float32; preservado o outro subavaliador MaxShield>10, as restrições de movimentação, bônus e apresentações. Descrição principal passa a escudo cheio. Não acrescentado polling ou refresh dos efeitos de Fearless, pois não mudam. Validação reduzida ao trecho novo:5 testes Fearless e2 integrações diretamente afetadas;7 aprovados. Sintaxe/TOML válidos; confirmar ativação ao completar o escudo e remoção ao sofrer dano no jogo. Sem pacote gerado/instalado.

## Grim — 0.1.1, 2026-11-13

Conferido no dump `GD_Assassin_Skills.Bloodshed.Grim`: SkillTypeKill, duração gerida pelo sistema nativo de kill skills, três linhas de efeito. Linhas0/1 são regeneração de escudo por ShieldMaxValue e stat de regeneração; linha2 é ActiveSkillCooldownConsumptionRate MT_Scale+.015 base/upgrade. Alterada somente linha2 para+.12/rank, GradeToStart1/intervalo1, equivalente a60% de Cooldown Rate em5/5. Não alterar escudo, duração, evento de eliminação ou textos/presentações nativos: o rodapé já resolve o atributo alterado.

Cache de COM agora compartilhado por Iron Hand e Grim, sem importar outros módulos. Flags independentes de configuração permitem assets tardios e falha isolada; somente features configuradas entram no refresh. Reconciliação de SkillEffects considera apenas efeitos com atributo e alvo real, pois Grim tem uma linha TARGET_None de apresentação que pode não existir no cache de gameplay. Se essa linha vier no snapshot, preservá-la sem retarget; não reconstruir a skill repetidamente por esse metadado ausente. Ranks e estado de kill skill não são escritos manualmente.

24 testes exclusivos Zer0 aprovados (8 Grim e16 adjacentes Iron Hand), incluindo rank/COM, preservação de escudo/gatilho/duração/UI, idempotência, assets pendentes, ativação/pausa e refresh estável sem rebuild. Sintaxe/TOML e links conferidos. Pendente confirmação no jogo dos valores12/24/36/48/60% e troca/remoção de COM. Nenhum pacote gerado/instalado; coop não validado.

## Implementação inicial — 0.1.0, 2026-11-13

Primeira habilidade autorizada: Iron Hand perde dano melee e recebe resistência nativa5%/rank. Conferido no dump nativo `GD_Assassin_Skills.Bloodshed.IronHand`: efeitos melee+.03 e HealthMaxValue_Player+.03, GradeToStart1/intervalo1, passive/on-foot, MaxGrade5, apresentações próprias0/1. Conservado o efeito de vida sem mudar coeficientes, inicializadores, restrições, ícone ou posição.

Substituído somente melee por nove canais de resistência MT_Scale−.05 base/upgrade, todos confirmados em AttributeDefinition.dump: normal, explosivo, impactos/status corrosivo/incendiário/choque e impacto slag. Isso usa a fórmula nativa: coeficiente25% em5/5 equivale20% de redução isolada. Não há multiplicador separado nem hook de dano. Apresentação melee nativa passa a Damage Reduction com inversão de sinal; apresentação de vida permanece intacta. Ranks/previews e cores ficam a cargo do motor.

Criados __init__.py e pyproject.toml, sem importar módulos dos outros personagens. Initialize recebe somente SkillTreeDef, conforme header nativo de PlayerSkillTree; não presumir parâmetro PlayerController. Configurar antes da árvore, tentar assets tardios no tick local e revalidar por identidade PC/mundo/pawn. Manutenção1s, um snapshot de ActiveSkills, cache de assinatura por COM/skill/rank/estado; não somar pontos nem escrever Grade. Corrigir layout de SkillEffects se ainda contiver melee antigo, com WeakPointers, rollback e parada após callbacks. Estados estáveis não reconstroem nem reenviam modificadores.

Viagem, troca de contexto e disable descartam identidades/caches, sem tocar em atores antigos. Como os dados nativos modificados permanecem na sessão, remover efeitos exige reiniciar. Runtime não possui varredura global, consulta por pellet, hook de combate ou escrita manual de vida.

Validação:16 testes exclusivos do código Zer0 aprovados, cobrindo configuração/idempotência, preservação da vida, nove canais/ranks1..11, apresentação, assets pendentes, layout inválido, COM/trocas/remoção, cache estável, callbacks/rollback, viagem e Initialize. Sintaxe/TOML/JSON/links válidos; nenhum teste de outros personagens executado e nenhum pacote gerado/instalado. Pendente no jogo: alocar1..5 pontos, comparar vida original, confirmar remoção do melee e novo valor/cor no rodapé e previews, depois equipar/trocar/remover COM com pontos investidos. Coop não validado.

Os registros abaixo descrevem a etapa histórica de planejamento, anterior ao código atual.

## Estado inicial — 2026-11-12

Autor: **Kgx37b9**. Etapa atual: documentação e planejamento, sem versão jogável.

Esta pasta contém apenas README.md, CHANGELOG.md, DEVELOPMENT.md e LICENSE.md. Nenhuma alteração de habilidade foi definida ou implementada. Não há `__init__.py`, `pyproject.toml`, hooks registrados ou pacote `.sdkmod` nesta etapa.

## Escopo e organização

O módulo será independente dos outros personagens e do EndgameQoLRebalance. Não importar módulos de gameplay desses projetos nem alterar seus arquivos para implementar mudanças do Zer0.

- **README.md**: apresentação, habilidades efetivamente alteradas, requisitos, instalação, compatibilidade, créditos e licença.
- **CHANGELOG.md**: histórico de versões e balanceamento aprovado.
- **DEVELOPMENT.md**: decisões específicas deste módulo, investigações e limites de validação.
- **LICENSE.md**: política de uso pessoal e autorização prévia para reutilização.
- [Guia central de conhecimento](../Conhecimento/GUIA_CONHECIMENTO_MODS.md): única fonte de aprendizados técnicos acumulados entre projetos. Registrar novos conhecimentos nele, sem criar outro guia local.
- [TESTES.md](../TESTES.md): diário central de verificações. Novos testes e consultas temporárias ficam em `../Suporte/`.

## Próxima etapa

1. Receber a primeira mudança de habilidade e seus valores, gatilhos, duração e condições de encerramento.
2. Identificar as definições e os atributos nativos envolvidos. Confirmar APIs nos dados ou headers disponíveis; não presumir caminhos de assets.
3. Criar a estrutura Python/manifest somente na etapa de implementação e declarar a versão inicial correspondente.
4. Implementar a mudança isoladamente, com descrição e textos do Mod Manager em inglês.
5. Executar apenas verificações do código novo e das integrações diretamente afetadas; depois solicitar o teste específico no jogo.

## Critérios de implementação e validação

- Preferir os efeitos e eventos nativos apropriados, com mudanças idempotentes e sem multiplicação repetida de coeficientes.
- Considerar pontos de mods de classe e os valores atual/próximo rank desde a primeira alteração de skill com múltiplos ranks.
- Separar feedback visual de efeitos de gameplay. Qualquer futuro ícone adicional deve respeitar slots nativos reservados e remapeados.
- Evitar varreduras globais, consultas por pellet, escritas estáveis repetidas e retenção de atores entre mapas. Usar referências fracas e caches limitados quando necessários.
- Invalidar estado em viagem, morte, troca de personagem, respec e desativação. Não reutilizar snapshots nativos após callbacks que possam reconstruir skills.
- Distinguir API confirmada, hipótese, teste simulado e confirmação no motor. Não anunciar suporte co-op sem testes.
- Documentar a procedência de contribuições e preservar as condições de material de terceiros; mudanças de nomes não demonstram independência de implementação.
- Não gerar ou instalar pacotes automaticamente sem pedido pertinente do autor.

## Validação desta etapa

Somente documentação criada. Conferir links locais, consistência entre os quatro documentos e identidade da licença com a política já adotada no workspace. Não executar suítes de gameplay para esta etapa e não apresentar uma versão como lançada.
## Atualizacao 0.1.3 - Resurgence

Preservados efeito, KillEvents e grafo nativos da cura por kill melee. Novo evento POST IncrementPlayerCriticalHitStat restaura 4% do escudo maximo por Grade efetivo, sem ICD. Linha TARGET_None e apresentacao privada exibem o valor sem aumentar capacidade. Rank vem do snapshot compartilhado de skills; nenhum scan por critico. Guardas de contexto, autoridade, pausa, FFYL, valores finitos e reentrada; sem acesso ao ator apos SetShieldStrength. Viagem/disable invalidam cache.

12 verificacoes focadas aprovadas, incluindo COM, criticos consecutivos, limite do escudo, contexto expirado e callbacks recursivos. Validacao no jogo pendente: alocar Resurgence, perder escudo e acertar criticos; conferir 20% em 5/5, COM e cura melee original. Sem pacote gerado.

## 0.1.5 - Velocity

Remover linha/apresentacao PlayerCriticalHitBonus; WeaponDamage=.05/rank, Bullet Speed nativa preservada. Inclusao na migracao compartilhada de efeitos remove critico obsoleto sem consultas novas. Cinco verificacoes focadas aprovadas, incluindo migracao e estabilidade de cache. Validacao no jogo com COM pendente.

## 0.1.6 - Many Must Fall

KillEvents de Skill_Deception possui KilledEnemyWithMelee com DamageSourceConstraint WillowDmgSource_Melee; grafo0 valida ManyMustFall em execucao. Remover apenas filtro de fonte (None), preservar nome interno do evento e grafo, DamageEvents e demais condicoes. Textos principal/feedback atualizados. Sem hooks extras, polling ou reativacao de Decepti0n ja encerrada. Seis verificacoes focadas aprovadas; testar eliminacao por granada/DoT enquanto Decepti0n continua ativa, comparando kill melee e habilidade nao alocada. Reiniciar apos atualizar; jogo pendente.

## 0.1.7 - Resurgence: cura em qualquer kill

KillEvents da propria Resurgence usa KilledEnemyWithMelee e filtro WillowDmgSource_Melee. Remover apenas DamageSourceConstraint, copiando evento/constraint; preservar nome interno esperado pelo grafo0, formula de cura, ranks e demais filtros. Nenhum hook de kill ou polling novo. Escudo por critico continua .04/rank. Quatorze verificacoes focadas aprovadas, sintaxe/TOML validos; testar kills de arma, granada e melee com vida faltante e pontos alocados. Motor pendente.

## 0.1.8 - Optics

Rework passivo: WeaponSpread -.10/rank, WeaponPerShotAccuracyImpulse -.12/rank e PlayerZoomTimeModifier -.10/rank, MT_Scale/TARGET_Self. Ultimo atributo confirmado em Expertise nativa; sem importar Axton nem copiar seu modulo. Remover os quatro efeitos antigos (zoom, duas formas de flinch e stat de recoil TARGET_None). Apresentacoes privadas usam estilo positivo nativo de Optics (SignStyle positivo, bDisplayAsInverse=False) e mostram Accuracy/Recoil Reduction/Aim Speed. Cache de COM existente migra layout anterior apenas quando necessario. Cinco verificacoes focadas aprovadas, sintaxe/TOML validos; confirmar no jogo com ranks1..5 e troca de COM. Sem pacote gerado.

## 0.1.9 - Like the Wind: esquiva ao mover e HUD nativo

Dump confirmado: LikeTheWind ja tem TRACKEDSKILL_Triggered, slot5 e icone de menu. Condicao PawnSpeed>1 resolve CurrentPawnSpeed no pawn. Preservar essas condicoes, registro e slot nativos; nao criar feedback nem Canvas. Outros slots nativos Zer0: CounterStrike1, KillConfirmed2, CriticalAscension3, BeLikeWater4, RisingShot6, Resurgence7, Innervate8, Fearless9 e ManyMustFall10. Assim o novo efeito usa o espaco ja reservado a propria skill.

Remover dano de arma/melee e grafo/helper legado de melee (helper tambem continha FootSpeed). Linha TARGET_None .05/rank e stat de chance substituem gameplay antigo. Migracao de SkillEffects usa manutencao compartilhada. Novo TakeDamage PRE valida dano positivo/finito, pawn/contexto local, autoridade, FFYL, velocidade atual, WeakPointer e SkillState ativo; Grade nativo consultado diretamente, sem soma COM. Sorteio independente min(1,.05*Grade), retorno Block; nenhum ICD adicional, varredura por dano ou cache forte de ator. Parado/pausado nao sorteia; native HUD acompanha SkillState. Viagem/disable/troca de dono invalidam referencia/contexto.

11 testes focados aprovados; sintaxe/TOML validos. Pendente motor: pontos1..5/COM, tomar dano movendo e parado, verificar icone nativo sem duplicacao e limpar em viagem/respec. Co-op nao validado; nenhum pacote gerado.

## 0.1.10 - Be Like Water: dois contadores e Amp temporario

Decisao confirmada pelo autor: mudar de estado remove imediatamente1 stack do estado anterior; a cada.5s perde mais1 enquanto o novo estado ganha1. Cada tipo conserva seu contador0..5 e os efeitos persistem enquanto houver stacks, inclusive durante transicao/reversao. Main Grade nativo determina .02/rank/stack. Removidos os antigos DamageEvents/grafo e efeitos dos dois helpers de ataque. Rodape tem Movement Speed per Stack e Amp Damage per Stack, TARGET_None sem gameplay antigo.

Movimento usa CurrentPawnSpeed>1, mesmo operando nativo confirmado em Like the Wind. Helper privado untracked aplica FootSpeed MT_Scale .02 com Grade=stacks*rank; nao reusa os dois antigos HUDs do mesmo slot4, evitando colisao de feedback. O pedido desta etapa e de gameplay/descricao; nao acrescentado HUD novo. Atualizar Grade somente quando conta/rank muda; depois de callback nativo, retornar e solicitar snapshot compartilhado fresco antes de outra escrita. Cache e referencias fracas nao retêm atores entre mundos.

Amp usa escopos PRE e POST_UNCONDITIONAL de FireAmmunition/SharedFireAmmunition/ExtraFireAmmunition. Um MT_PostAdd temporario em InstantHitDamage acrescenta dano_atual*.02*Grade*stacks. Nao e WeaponDamage MT_Scale. Mesmo weapon em wrappers aninhados nao recebe Amp novamente; pellets usam o mesmo escopo. Cache do modificador e fraco/limitado; cleanup remove o modificador exato, sem restaurar um escalar que apagaria outros mods. Falhas parciais tambem limpam o escopo. Viagem e disable removem runtime com dono valido, inclusive na pausa; Destroyed apenas invalida frames/referencias, preservando profundidade dos POSTs pendentes e sem acessar atores de saida. Nao continuar leituras nativas apos callback que resetou o estado.

19 testes focados aprovados (16 novos e3 integracoes adjacentes), sintaxe/TOML validos. Pendente no jogo: construir5 stacks em2.5s movendo/parado, verificar bonus50% em5/5, transicao4->3 enquanto novo0->1, trocar COM e viajar. Co-op nao confirmado; sem pacote gerado ou instalado.

# Precision: filtro de inimigo corrigido em0.1.19 (2026-11-15)

Captura14:28:30UTC: crítico chegou ao Reflect com bCanReflect=True, Grade5 ativo, cache recente, identidade/local/contexto válidos e autoridade3. target_cache retornou ausência de alvo; a consulta só mostrou como candidato um ator sem vida a~67mil unidades, usando o filtro incorreto. Headers nativos Engine.PawnAllegiance.EOpinion confirmam Enemy=0, Neutral=1, Friendly=2. _precision_has_target comparava com2 e descartava inimigos reais.

Configuração agora resolve EOpinion.OPINION_Enemy uma vez e guarda apenas o inteiro; não há nova consulta nativa por alvo/hit. Consulta temporária e mocks usam os valores corretos. Regressões aceitam inimigo0 e rejeitam neutro1/amigo2, inclusive amigo antes de inimigo na lista. Os21 testes focados passaram. Sem alterações de dano, alcance, duração do escopo, visibilidade ou recursão. AST/TOML e versão0.1.19 conferidos; nenhum pacote gerado/instalado. Confirmar com a fonte atualizada, após reiniciar, críticos próximos de outro inimigo vivo.

Observação de escopo: a busca também localizou comparações fixas com2 em outras rotinas do Zer0 (dano de Be Like Water, acúmulos de At One with the Gun e Death Mark de Unf0reseen). São candidatas à revisão separada; não foram alteradas ao corrigir Precision.

## At One with the Gun HUD 1.0.4 (2026-11-16)

Feedback visual ZR_ChargeHUD sob skill original, icone original, Grade1..10 e CustomStackCount privado baseado em Grade. Sem efeitos/constraints/eventos de gameplay, DurationInfinite, nao sujeito a regras deGradeCOM. Em10 o proximo tiro esta preparado, sem nova cor ou timer. Ao consumir cargas o estado existente zera e visual e desativado; nao alterar agrupamento de tiros/pellets/projeteis ou danoamp.

Fabrica nativa _counted_hud_feedback extraida da configuracao de Water, preservando seus dois indicadores. One usa sincronizacao/flags/cache independentes e o mesmo alocador de slots logicos/remapeados, registros inativos/filhos e icones. Contagens estaveis nao reescrevem nativo; reconciliacao limitada1s para recuperacao de movie/menu. Chamado no PlayerTick existente, antes dos demais callbacks, retornando apos escrita que invalida snapshots. Inativo nao consulta movie. Cleanup de One remove visual antes do reset; fullHUD nao toca stacks/dano.

40 testes afetados/adjacentes aprovados (6OneHUD+OneWithGun/WaterHUD34), incluindo1..10, carga consumida, coexistencia com ambosWater, HUDcheio, idle/estavel e respec/cleanup. Sintaxe/TOML validos. Confirmar no motor contagem ate10, tiroamp, menu e viagem; sem pacote/instalacao.


## 2026-11-20 - Zer0: At One with the Gun, criticos e multiplos projeteis

Causa confirmada no codigo: count_one_hit encerrava o token no primeiro impacto valido e sempre somava uma carga; bWasCrit nao era consultado. Nao era apenas uma disputa na ordem dos pellets: o critico nunca tinha credito diferenciado.
Correcao: credito acumulado por token de disparo, uma carga normal ou duas no total com critico. Normal seguido de critico adiciona somente a diferenca; critico primeiro encerra o token. Pellets normais repetidos retornam antes das leituras de jogador/inimigo/skill. Nenhum novo hook, timer ou busca global. Preservados registros fracos/limitados, validacao de fonte e autoria, ciclo de empoderamento, limite dez e HUD.
Validacao offline: 32 testes focados (test_zer0_one_with_gun e test_zer0_one_hud) passaram, incluindo ordem normal/critico, criticos repetidos, projeteis atrasados entre disparos, ciclo antigo, dano zero e teto dez. Sintaxe e TOML conferidos. Versao mantida em1.0.4. Validacao no motor pendente: apos instalar e reiniciar, tiro isolado normal deve gerar1 e tiro com ao menos um critico2 no total, independentemente dos pellets; com dez cargas o proximo tiro consome o bonus sem recarregar o contador.


## 2026-11-20 - Zer0: Resurgence e Like the Wind

Resurgence: cura por kill passa de4% para6% por ponto. Configuracao copia a linha e os dois valores nativos (BaseModifierValue/PerGradeUpgrade), multiplica suas escalas por1.5 a partir de escala original memorizada; preserva atributos/resolvers da formula dependente de vida. Reconfiguracao nao acumula fator. Linha de escudo por critico continua4%, kill graph e gatilho por qualquer kill preservados. Like the Wind passa de.05 para.06 por rank na constante compartilhada gameplay/descricao (30% em5/5); cap100%, HUD e movimento preservados.
26 testes focados passaram por importacao direta: Resurgence16 e LikeTheWind10. Uma tentativa inicial de discovery dos mesmos arquivos importou indevidamente o pacote auxiliar bsabt_revisao e falhou por ausencia de unrealsdk fora do jogo; corrigido o comando para modulos explicitos, sem modificar BSABT. AST/TOML e pacote de seis arquivos conferidos. Versao1.0.4 mantida; nenhuma instalacao na pasta do jogo. Validacao nativa dos novos valores pendente.


## 2026-11-20 - Grim: regeneracao de escudo1.1%/s por ponto

Aumentadas as duas linhas nativas de regeneracao/gameplay e apresentacao de0.7% para1.1% por segundo por rank (5.5%/s em5/5). Copias das formulas Base/PerGrade preservam atributos e initializers; escalas originais escalares memorizadas e fator11/7 evitam multiplicacao cumulativa ao reconfigurar/retornar ao mapa. Sem novo hook ou timer, sem alterar duracao/gatilho ou cooldown10% por ponto. Oito testes focados passaram, cobrindo valores por rank, apresentacao, idempotencia e COM. AST/TOML/pacote conferidos, versao1.0.4 mantida; teste nativo pendente. Nenhuma alteracao na instalacao do jogo.


## 2026-11-20 - Fearless e Like the Wind: balanceamento

Fearless escudo cheio mantido; linhas nativas WeaponDamage=.04/rank e WeaponFireInterval=-.07/rank, Base/PerGrade, sem novos efeitos de gameplay. Atualiza apresentacoes nativas pelos mesmos atributos. Preserva alvo/tipo de modificador, constraints e tolerancia de escudo cheio. Layout de dois atributos validado antes das alteracoes; cache invalidado apenas se linhas mudarem. Like the Wind retorna.05 por ponto (25% em5/5), HUD/limite100% preservados. Quinze testes focados Fearless/LikeTheWind passaram; fixture compartilhada agora representa linhas reais de Fearless em vez de marcador string. AST/TOML/SDKmod conferidos; versao1.0.4 mantida, sem instalar no jogo. Valores aguardam validacao nativa.


## 2026-11-20 - Fearless5% e Unf0reseen75..300%

Fearless dano de arma=.05 por rank, cadencia7% e escudo cheio preservados. _unforseen_bonus retorna.75+(clamp(stage,1,90)-1)*2.25/89: bonus+75% no nivel1 e+300% no stage90(OP10), fatores finais1.75x e4x sobre formulas nativas escaladas pelo jogo. Mesma progressao linear no dano direto e DoT; raio/puxao/DeathMark e restauracao de formulas preservados. 25 testes focados passaram, incluindo extremos/ponto medio e dano/status/restauracao/nesting. AST/TOML/pacote conferidos; versao1.0.4 mantida, sem instalar. Validacao no motor pendente.


## 2026-11-20 - Segundo crash Save & Quit e correcao candidata1.0.5

Novo crash15:49:46local em Zer0/Save & Quit; Windowsc0000005, PID5048, Borderlands2.exe+0x36b94. Dump confirma leitura0x3f800048 via mov eax,[eax+0x48], eax=0x3f800000(float1.0). Primeiro crash14:01:37 foi na mesma rotina+0x36bea, mov edx,[eax+0x34], eax=0x3d4ccccd(float.05). Corpo nativo consulta classe emUObject+0x34 e percorre SuperField+0x48 antes de chamada virtual; dados esperados como ponteiro cont?m floats. Evidencia consistente com referencia de objeto invalida/reutilizada na travessia/limpeza nativa, sem identificar quem a originou. Faulthandler sem framePython; ultimo SDK suspensaoHUDMaya nao prova culpa. Segundo dump/pilha continua executavel nativo, sem traceback.

Fragilidade concreta encontrada emAtOne: _precision_object("AttributeModifier", weapon, "ZR_OneShotAmp") usavaKEEP_ALIVE, enraizando helper sob arma transitoria. MesmoaposRemoveModifier o objeto permanente conservaOuterarma. _one_modifier_cache guardava apenas ultimaWeakPointer, mas nao removia enraizamento dos anteriores. Relacao causal com os dumps ainda nao demonstrada; nao declarar crash resolvido.

Correcao1.0.5: _configure_one_with_gun cria/reutiliza8helpers ZR_OneShotAmp_0..7 sobSkillDefinition estatico. begin_one_shot usaindice por profundidade de framevalido, semlookup/construct por tiro, falhafechada se exceder8, semgastarbonus. Remove cache porarma. Frames/RemoveModifier seguem fracos e retornam ao estadooriginal. Resetdescarta poolPython seminspecionaratores saindo. Nenhumrootnovo sobarma/world. Nao alteradosnumeros/cargas/HUD nemoutrosmodulos.

36 testes focados passaram: propriedadeOuterestatica,8helpers,25identidadesdearma semnovascriacaobuscas, poolausente, resetsemacessosaRemoveModifier e regressao de tiros/criticos/HUD. AST/TOML/CRC/sourcebytes conferidos. DependenciaCapstone5.0.9 instalada somente emSuporte/.crash-analysis para leituraexterna dedumps; nao pertenceaopacote nem cria dependencia dojogo. Semnovacaptura emjogo, seminstalar SDKmod. Necessarioreiniciocompleto paraeliminarobjetosantigos e testar variasrodadas: carregar,atirarconsumindoAmp,Save&Quit,reentrar. Se repetir, comparar comZeroRebalancedesativado apos reiniciar e capturardumpcompleto para identificarreferenciapendente.


## 2026-11-20 - Resurgence: cura fixa6% da vida maxima por rank

Confirmacao explicita do autor: preservar6% por ponto(valorpretendido), nao5% nem4%, mudar apenasbase devida faltante paraMaxHP e corrigirdescricao. _configure_resurgence resolve DesignerAtt_Resurgence_HealthRestorePerLevel eBPDnativoevalida layoutcompletoantesdemutar:5nos nomeados,9variaveis,19indices,14links; inputA deSimpleMath258 emlink3 aponta paraConsolidatedLinkedVariables[8]. Troca somenteessa celula int de4(missingHP)para6(MaxHP), semreescreverWrappedArraysdegrafos/seqs. O calculoinutil deMissingHP permanece masnao e usado nacura; demaisnos/outputs/evento/HUD preservados.

DesignerBaseValue=.06 semresolverextra; verdadeirocoeficiente usado porSimpleMath257. LinhametadadosTARGET_NoneHealthPassiveRegenerationRate agora .06Base/PerGrade sematributo/initializer, apenasdescricao. Removidosfator1.5 ebaselineescala obsoletos queafetavamapresentacao,naocura. Descricao superior restauraMaximumHealth; inferiorHealthRestoredperKill. Escudocritico4%/rankinalterado; ReTriggerDelay.1s eHUD2s preservados. Formula: cura=HPmax*.06*GradeEfetivo, ateHPmax. Em5/5cura30%MaxHP por kill, qualquerque sejaHPfaltante.

54 testes focados/adjacentes passaram: Resurgence18,OneWithGun/HUD36. FixtureagorarepresentaBPDnativocapturado; exercita inputreal dografo+Designer, ranks1/5/11,HPdiversas,cap, idempotencia, layoutinesperado/missingassetsemalteracoes eescudocritico. AST/TOML/CRC/sourcebytesvalidados; versao1.0.5preservada. Semalteracao do jogoinstalado/emexecucao. Confirmacaonativa dacurapor kill aposinstalacao/reinicio ainda pendente; nao usar testesmetadados comoevidenciadecurareal novamente.


## 2026-11-20 ? Zer0 1.0.6: revis?o final de estabilidade/performance

 20/11/2026. Escopo: caminhos de disparo/dano, HUD, manuten??o, grafos e troca de sess?o. Valores e efeitos das habilidades preservados.

## Corre??es

- `_configure_be_like_water` prepara os 48 modificadores poss?veis (oito profundidades ? seis fontes) sob defini??es est?ticas. `_water_damage_rows` n?o faz buscas nem cria objetos durante dano; falta de slot falha com limpeza do escopo. O limite de profundidade existente continua em oito.
- `_change_kill_confirmed_count` e `_apply_water_movement` reutilizam defini??es est?ticas obtidas na configura??o. `_reset` invalida essas refer?ncias; n?o s?o caches de personagens/inimigos.
- `guard_precision_reflection` valida cr?tico/reflex?o existente antes de procurar alvos. Uma recusa expl?cita de `AddModifier` aciona rollback, restaura raio/modificadores e impede publicar um resultado n?o aplicado.

## Demais verifica??es

- At One with the Gun conserva o pool est?tico de oito modificadores da 1.0.5; nenhuma cria??o por tiro ou helper permanente com arma como Outer.
- Registradores de proj?teis e fontes continuam limitados; refer?ncias de atores s?o fracas e validadas por mundo/dono. Campos tempor?rios t?m restaura??o no caminho incondicional; reset de mundo evita reaproveitar atores antigos.
- HUD atualiza por mudan?a de contagem e verifica??o de recupera??o limitada; mant?m o alocador de slots. N?o foram adicionados hooks, timers, buscas globais ou consultas de ActiveSkills por impacto.
- Revis?o est?tica n?o encontrou execu??o din?mica, acesso a arquivos/rede ou busca global `find_all` no m?dulo. Isso n?o equivale a uma prova formal de aus?ncia de vulnerabilidades nativas.
- O ?ltimo crash examinado ocorreu em bifrost.dll. Esta revis?o n?o demonstra sua corre??o nem substitui o teste offline. Offline Helpers permanece um pacote independente.

## Valida??o e limites

129 testes focados/adjacentes passaram: Kill Confirmed, Be Like Water, seu dano/HUD, Precision e At One with the Gun/HUD. Novas regress?es cobrem oito escopos aninhados com seis fontes sem aloca??o/busca, pool ausente, cache/invalida??o, aus?ncia de busca em impactos ineleg?veis e recusa expl?cita do modificador. AST, TOML e integridade/igualdade do conte?do do SDKmod conferidos.

A primeira execu??o da nova regress?o detectou que a guarda de recusa ainda n?o havia sido inserida no ponto correto (`current.AddModifier`); corrigida antes da execu??o final aprovada. Nenhuma falha pendente desses testes.

N?o houve medi??o de FPS nem confirma??o nativa nesta revis?o. Validar ap?s reiniciar: cr?ticos/ricochetes consecutivos, movimento/parada de Be Like Water, HUD e tiro empoderado, Resurgence, abertura das habilidades e v?rios Save & Quit. Coop permanece sem valida??o. O alerta anterior de Unf0reseen sem centro de clone foi tratado e anterior ao crash; n?o foi usado como causa confirmada nem alterado sem reprodu??o.

Pacote atualizado em `Suporte/Builds/Zer0Rebalance.sdkmod`; nenhuma c?pia instalada do jogo foi substitu?da nesta revis?o.

## 2026-11-20 - Unf0reseen: bonus fixo e carga nativa de Decepti0n

Substitui a progressao extra por nivel (+75% a +300%) por +50% fixos. O escalamento de nivel nativo continua intacto. A leitura externa somente de leitura da sessao confirmou Skill_Deception: cinco etapas, Delay_161 e Skill_ActionSkillDamageBuffStack; a explosao de Skill_Stealth.OnDeactivated acontece antes de Behavior_DeactivateSkill_40 remover o helper. Evidencia em Suporte/zer0_deception_damage_native.json e leitor inspect_zer0_deception_external.py.

O PRE ja existente de Unf0reseen le uma vez Att_NumberOfDamageBuffs.GetValue(controller), limitado a 0..5. Fator = 1.5 * (1 + 0.4 * stacks): 1.5x, 2.1x, 2.7x, 3.3x, 3.9x, 4.5x. Portanto o ganho temporal chega a +200% sobre a base ja aumentada em 50%. Segue as etapas e renovacoes nativas; nao inventa outro temporizador, nao altera grafo/duracao/MMF e nao adiciona bonus a outros danos do personagem. Aplica ao dano direto e StatusEffectDamage, com restauracao no POST/reset e isolamento de escopos aninhados. Atributo estatico resolvido somente na configuracao; dependencia ausente adia a configuracao e valor nao finito aborta sem deixar formula alterada.

38 testes focados/adjacentes de Unf0reseen e Many Must Fall aprovados. Cobertura inclui estados 0..5, limites, retorno GetValue em tuple, reinicio dos stacks, independencia do nivel, dano/status/restauracao/nesting e reset. AST/TOML e pacote conferidos. Sem instalacao na sessao aberta. Validacao de dano real: reiniciar com o pacote, comparar cancelamento antecipado e termino natural de Decepti0n, incluindo renovacao por MMF; confirmar puxao e Death Mark. Testes offline nao comprovam o resultado no motor nem coop. Versao 1.0.6 mantida.

## 2026-11-20 - Ajuste numerico: raio de Unf0reseen e cura de Resurgence

Unf0reseen: raio compartilhado do puxao e dano reduzido em 20%, de 2000 para 1600 UU (20 para 16 m). Bonus fixo de 50%, carga nativa ate +200%, Death Mark e restauracao de formulas preservados. Resurgence: RESURGENCE_HEALTH_PER_RANK=.05, aplicando 5% da vida maxima por ponto por eliminacao (25% em 5/5) no coeficiente nativo e na apresentacao; recuperacao de escudo em criticos permanece 4% por ponto. README/CHANGELOG atualizados, versao mantida. 42 testes focados de Unf0reseen/Resurgence passaram; esperado antigo de 30% corrigido para 25% em 5/5. AST/TOML e pacote de seis arquivos conferidos; sem instalacao na sessao aberta e validacao no jogo pendente.

## 2026-11-21 - Unf0reseen 14 m e Fearless com qualquer escudo

Raio compartilhado de dano/puxao de Unf0reseen: 1400 UU (14 m), mantendo os bonus e demais comportamentos. Fearless: condicao nativa ShieldCurrentValue > ShieldMaxValue * 0, sem polling ou novos hooks; zero escudo desativa, qualquer valor positivo ativa. Bonus por rank: WeaponDamage +.04 e WeaponFireInterval -.05 (mesma representacao nativa usada antes). Descricao e log atualizados. Preservados constraints, apresentacoes e suporte a ranks de COM. 46 testes focados/adjacentes aprovados, cobrindo escudo cheio/parcial/zero/positivo minimo, ranks 1/5/11, idempotencia, raio/puxao e restauracao do dano de Unf0reseen. AST/TOML e pacote de seis arquivos conferidos; versao mantida, sem instalacao automatica. Validacao no jogo pendente.

## 2026-11-21 - Raio na descricao inferior de Unf0reseen

Apresentacao nativa confirmada por leitura externa: Unforseen.AttributePresentationDefinition_2. Acrescentado Damage Radius: 14 meters ao footer existente; derivado de UNFORSEEN_PULL_RADIUS/100, sem duplicacao em reconfiguracoes e sem alterar valores de dano. 24 testes focados aprovados; AST e pacote conferidos. Aparencia no jogo pendente; versao mantida.

## 2026-11-21 - Tw0 Fang: disparo adicional sem custo de municao

Dados nativos lidos em Suporte/zer0_two_fang_native.json: TwoFang usa WeaponExtraShotChance, 6% por rank, sem BehaviorProvider. A classe WillowWeapon expoe ExtraFireAmmunition, SharedFireAmmunition e ConsumeAmmo. Implementacao mantem o sorteio nativo e os ranks efetivos: configura somente a descricao e guarda a definicao estatica. No PRE exclusivo de ExtraFireAmmunition, valida Zer0 local/autoridade/dono/mundo/arma atual/vida/rank e pente com municao; guarda ShotCost e zera somente durante essa chamada. ConsumeAmmo e bloqueado somente para a mesma arma no escopo. POST_UNCONDITIONAL restaura custo inclusive quando outro hook bloqueia o disparo; reset/disable limpam escopos mantendo tombstones para callbacks pendentes. Referencia de arma e fraca, dono e identidade primitiva; nunca restaurar arma de outro mundo/personagem. Custo modificado por outro sistema nao e sobrescrito na saida. Limite de oito escopos elegiveis, sem varredura de atores/skills, timers ou polling adicional; GetSkillGrade consultado uma vez por disparo extra elegivel. Nenhuma reposicao manual de cartuchos ou alteracao da reserva.

48 testes focados/adjacentes de Two Fang e At One with the Gun/HUD passaram: custo inicial preservado, extra gratuito, custos de 1/2/4 cartuchos, reentrada, arma alheia, sem rank, cliente/pausa/FFYL/pente vazio, reset, mundo alterado e conflito de custo. AST/TOML e pacote de seis arquivos conferidos, versao mantida. Nao instalado na sessao aberta. Despacho nativo e consumo real ainda precisam ser validados: reiniciar com pacote, usar arma sem burst e disparar tiros isolados; ao Two Fang ativar, os dois disparos devem descontar somente o custo de um tiro no pente/reserva. Confirmar com shotgun e arma de custo multiplo, e conferir que tiros seguintes continuam cobrando. Coop permanece nao validado.

## 2026-11-21 - Zer0 1.0.7: Two Fang despachado pelo estado WeaponFiring

Causa comprovada pela captura de 25 s: 27 chamadas de FireAmmunition, 37 de SharedFireAmmunition/ConsumeAmmo e 10 extras em WillowGame.WillowWeapon:WeaponFiring.ExtraFireAmmunition. ZERO chamadas ao metodo base ExtraFireAmmunition anteriormente interceptado. Todos os procs estavam com depth=0/eligible=0, logo a protecao nunca entrava. Exemplo inicial: tiro normal clip22->21 total83->82; extra via WeaponFiring clip21->20 total82->81. Consumo do pente acontece antes de ConsumeAmmo, que reduz o total; reforca a necessidade de custo zero mais guarda de consumo.

Correcao minima: adicionar o caminho de estado comprovado aos decorators PRE e POST_UNCONDITIONAL de begin_two_fang_extra/finish_two_fang_extra. Preservar o caminho base como compatibilidade, com mesma guarda de aninhamento. Nao modificar os hooks de At One with the Gun nem outras habilidades. Evidencia completa: Suporte/zer0_two_fang_dispatch_20261121.json. Regressoes agora conferem decorators reais via AST e simulam a sequencia normal/extra/normal observada, garantindo custo so dos tiros normais, pente/total coerentes e restauracao do ShotCost. 50 testes focados/adjacentes passaram; AST/TOML e pacote1.0.7 conferidos, sem instalar na sessao aberta. Valida??o no motor da correcao pendente: instalar pacote com jogo fechado, reiniciar e repetir tiros isolados; disparo duplo deve cobrar uma vez. O probe existente pode conferir novamente o estado e consumo.

Licao: funcoes Unreal dentro de estados podem sobrescrever o metodo base com outro caminho de hook. Nao concluir funcionamento por nomes/metodos base ou testes que chamam diretamente callbacks; registrar _path_name real e cobrir o despacho nativo confirmado em regressao.

## 2026-11-21 - Grim: cooldown rate 8% por ponto

GRIM_COOLDOWN_PER_RANK reduzido de .10 para .08 (40% em 5/5), mantendo regeneracao de escudo de 1.1% por segundo por rank, gatilho e duracao nativos. README, CHANGELOG e log de configuracao alinhados. Oito testes focados de Grim aprovados; AST/TOML e pacote1.0.7 conferidos. Sem instalacao na sessao aberta.
