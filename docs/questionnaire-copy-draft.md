# Owner questionnaire draft — Q3–Q14 (final copy), TEMP working file

Source of truth for the registry rewrite. Q1/Q2 and Q15 are unchanged.

Structural notes (from the reviewing engineer, not the owner):
- Use EXACTLY the option counts below. Some nodes change count vs the current
  registry (Set A Q5 3→4, Set A Q7 6→5, Set A Q9 2→3, Set D Q7 3→4). That is
  intended.
- Modifiers are absolute: `micro+20` → `micro=20`. `-` means no modifier
  (all zeros). `mystiko+20/macro+60` → `mystiko=20, macro=60`.
- `next=Q4A` is a branch arrow; `next=-` means no branch.
- Preserve the CURRENT registry's `next` on the option at the same index when
  the draft does not give an arrow; new options get no branch. Never leave a
  branch node unreachable.
- Set A Q8 gate: keep the two-option gate (Yes → Q8A, No → Q8B). The owner's
  "What matters most when the game calculates success with stats?" becomes the
  Q8A text; Q8's text is "Does the game calculate success using stats (i.e. HP,
  damage, levels, gear)?".
- keyPhrase (TypeScript registry only): pick a short verbatim phrase (2–5
  words) from each question that carries it; it must be an exact substring.

---

## Set A — Sensory

### Challenge

Q3 text: How much does precise physical input affect what happens?
- A lot: Missing a dodge, shot, combo, jump, or timing window can quickly cause failure or heavy damage. :: micro+20
- Somewhat: Timing and accuracy matter, but mistakes are usually recoverable. :: micro+15
- A little: The game rewards accurate input, but the timing is fairly forgiving. :: micro+10
- Barely: Actions work almost the same regardless of exactly when the player presses. :: micro-10
- Not at all: The game mainly uses turns, menus, clicks, or choices rather than physical timing. :: micro-30

Q4 text: How much does the order of actions matter?
- A fixed order matters :: next=Q4A
- The player chooses the order :: next=Q4B

Q4A text: What happens if the player does things in the wrong order?
- Fails badly: The objective fails, the run resets, or there is a major penalty. :: macro+5
- Slight setback: It still works, but wastes time or gives a worse result. :: macro+2
- No difference: The player can do things in any order with essentially the same result. :: macro+0
- The game blocks it: The next step simply cannot happen until the previous one is completed. :: next=Q4C

Q4B text: How important is choosing your own order?
- Very important: A poor order can make success much harder or cause a timer/resource problem. :: macro+10
- Helpful: A good order makes things easier, but almost any order works. :: macro+2
- Not important: The order barely changes anything. :: macro+0

Q4C text: Can the player's choices change what happens later?
- Yes, significantly: Different choices can change routes, mechanics, characters, or endings. :: macro+10
- No: Everyone follows essentially the same path and gets the same outcome. :: macro-30

Q5 text: How much does the game hide useful tricks or rules?
- A lot: Players can discover hidden interactions, unusual combos, secret rules, or tricks that make them substantially better. :: mystiko+10
- A little: There are some secrets or tricks, but most important rules are obvious. :: -
- Almost none: The game tells the player nearly everything they need to know. :: mystiko-10
- None: There is effectively no hidden gameplay knowledge to discover. :: mystiko-15

Q6 text: How much fast or continuous input does the game demand?
- Very high: The player is constantly moving, aiming, clicking, dodging, or pressing buttons quickly. :: micro+80
- High: There is frequent physical input, but regular breaks exist. :: micro+65
- Low: Inputs are occasional or comfortably paced. :: micro+20
- Very low: Most actions are slow, menu-based, or turn-based. :: micro-20

Q7 text: How important is predicting what happens next?
- Essential: Players must read enemy attacks, movement, hazards, or patterns before they happen. :: mystiko+80
- Mostly stats: Prediction helps, but stronger equipment, characters, or resources usually matter more. :: mystiko+20/macro+60
- Mostly reaction: The player mainly reacts after something happens. :: mystiko-10/micro+60
- Sometimes useful: Prediction helps, but basic reactions are usually enough. :: mystiko+10
- No threats to predict: There are no meaningful enemies or moving hazards. :: mystiko-100

Q8 text: Does the game calculate success using stats (i.e. HP, damage, levels, gear)?
- Yes :: next=Q8A
- No :: next=Q8B

Q8A text: What matters most when the game calculates success with stats?
- Player skill wins: Good aim, movement, timing, or execution can overcome better numbers. :: micro+35/macro+5
- Both matter: Stats create a major advantage, but skilled play can still overcome some of it. :: micro+15/macro+70
- Stats win: Level, gear, damage, or other numbers overwhelmingly decide the outcome. :: macro+95

Q8B text: Does the game mainly revolve around repeating a physical action?
- Yes :: next=Q8C
- No :: micro-20 :: next=Q8D

Q8C text: How much of the game is about mastering that action?
- Almost all of it: Mastering the action is basically the whole game. :: micro+100
- Most of it: The action is the main activity, with a few supporting systems. :: micro+50
- Only one part: The action exists, but other systems are equally or more important. :: micro+5

Q8D text: Does the game use text, dialogue, or narration heavily?
- Yes :: next=Q8E
- No :: next=Q8F

Q8E text: During those sections, how much physical control does the player still have?
- No physical control: The player mostly reads, chooses, or waits. :: mystiko+10
- Full physical control: The player is still moving, aiming, driving, etc. :: micro+10
- Both: The player must follow the story while still reacting to what is happening. :: micro+5/mystiko+5

Q8F text: Does the game require solving puzzles or figuring things out?
- Yes: Progress depends on solving puzzles, clues, or deductions. :: mystiko+40
- No: Navigation and objectives are mostly straightforward. :: mystiko-10

### Reward

Q9 text: What kind of unlockable rewards does the game provide?
- Looks and cosmetics :: next=Q9A
- Useful gameplay rewards :: next=Q9B
- Neither :: micro-20/macro-20

Q9A text: How are the cosmetics mainly earned?
- Playing the game: Completing activities, challenges, chapters, or grinding earns them. :: micro+100 :: next=Q9C
- Paid or random: They mainly come from purchases, battle passes, loot boxes, or gacha. :: micro+25/macro+30 :: next=Q9C
- Both: Players can earn cosmetics and also buy them. :: micro+40/macro+30 :: next=Q9C

Q9B text: What kind of progression reward matters most?
- Bigger numbers: Better damage, stats, levels, equipment, etc. :: macro+80
- New abilities: Unlocking movement, exploration, or new ways to interact with the world. :: mystiko+70/macro+20

Q9C text: Can players trade those cosmetics?
- Yes: Players can buy, sell, or trade them. :: macro+40 :: next=Q9D
- No: They stay with the player's account/save. :: micro+30/macro+20 :: next=Q9D

Q9D text: Are there also gameplay-changing unlocks?
- Yes :: next=Q9E
- No :: micro-20/macro-20

Q9E text: How much do those unlocks change gameplay?
- A lot: They add major abilities or significantly increase power. :: micro+20 :: next=Q9F
- Somewhat: They offer different but reasonably balanced ways to play. :: micro+10/macro+20 :: next=Q9F
- Not at all: They mainly exist for appearance, story, or collection. :: macro-10/mystiko+15 :: next=Q9F

Q9F text: Does the game have a rank or leaderboard?
- Yes, it's a major part of the game :: macro+90
- Yes, but it's secondary :: macro+20/mystiko+50
- Yes, but hardly anyone cares about it :: macro+5/mystiko+50
- No :: macro-15

Q10 text: What gives the game most of its moment-to-moment satisfaction?
- Physical feel: Movement, aiming, hitting, driving, shooting, jumping, cleaning, etc. feel satisfying. :: micro+90
- Beautiful sensory experience: Music, visuals, atmosphere, sound, or effects are the main reward. :: micro+50/mystiko+20
- Discovering things: Exploration, secrets, strange events, or new places provide the biggest payoff. :: mystiko+100
- Making a clever setup work: Builds, combinations, planning, or systems suddenly pay off. :: macro+80
- Playing together: Coordination with other players creates the main payoff. :: macro+30

Q11 text: If the player's progress disappeared, what would be the biggest loss?
- Cosmetics and collection :: micro+80
- Personal world/space :: mystiko+60 :: next=Q11A
- Rank and competitive status :: macro+100
- Money spent :: micro+30/macro+30
- Records and best times :: micro+40/macro+60
- Shared memories and things built with others :: micro+40/mystiko+30

Q11A text: How relaxing is the game designed to be?
- Almost completely relaxing: Very few meaningful failure states or pressure. :: mystiko+200
- Mostly relaxing: Calm overall, but some pressure, timers, or resource problems exist. :: mystiko+50
- Not actually relaxing: It may look cozy, but failure and pressure still matter. :: micro+20/macro+10

Q12 text: How much does fatigue affect physical play?
- A lot :: next=Q12A
- Very little because the game is relaxing :: micro-10
- Neither :: micro+0

Q12A text: What becomes harder when tired?
- Paying attention :: micro+10
- Handling lots of sensory information :: micro+20
- Reacting quickly :: micro+10/macro+50
- Staying aware of what is happening :: micro+15
- Rapid repeated input :: micro+17

Q13 text: What makes the game interesting to watch?
- Amazing skill: Watching highly skilled players do things most players cannot. :: micro+20/macro+50
- Smart play: Watching clever builds, routes, strategies, or decisions. :: micro+50/macro+10
- Unexpected chaos: Funny, strange, or unpredictable things happen. :: mystiko+10
- New discoveries: Watching players find new tricks, builds, or interactions. :: micro+23
- Competition: Watching coordinated high-level matches. :: micro+15/macro+50
- Relaxation: Watching the game is calming even when playing it is demanding. :: mystiko+29

Q13B text: If it is not especially interesting to watch, why not?
- Hands-on feel: The fun mostly comes from personally controlling it. :: micro+67
- Slow personal pace: Reading, planning, or doing things at your own pace is hard to make exciting as a spectator. :: mystiko+5

Q14 text: What is the game's biggest weakness?
- Cheating/exploits :: micro+30/macro+60
- Technical problems :: micro+65/mystiko+20 :: next=Q14A
- Bad monetization :: macro+80
- Bad balance :: micro+35/macro+35
- Repetitive gameplay :: micro+10 :: next=Q14A
- Too much grinding :: micro-22 :: next=Q14A
- Too much random loot :: macro-2 :: next=Q14A
- Too few players :: mystiko+19 :: next=Q14A

Q14A text: What is the game's most underrated strength?
- Achievements/challenges :: macro+44
- Game feel :: micro+31
- Unique ideas :: mystiko+77
- Cross-platform progression :: macro+15
- Art/animation/visuals :: micro+15/macro+5
- None :: +

---

## Set B — Fantasy

### Challenge

Q3 text: How much does real-time control matter during difficult situations?
- Very high: Dodging, aiming, timing attacks, platforming, or movement accurately is essential. :: micro+85
- Moderate: Real-time action matters, but mistakes can often be recovered from. :: micro+35/macro+45
- Very low: The game mostly uses turns, menus, cards, or automatic actions. :: micro-40/macro+50
- Low but stats matter: Simple actions are enough, while levels, gear, or abilities do most of the work. :: micro+15/macro+65

Q4 text: When the game becomes difficult, what usually gets the player past it?
- Better preparation: Change the character, equipment, deck, resources, or setup. :: next=Q4A
- Better execution: Learn attacks, patterns, timing, or movement. :: next=Q4B
- A different approach: Use the environment, stealth, dialogue, building, or another system. :: next=Q4C

Q4A text: How much can preparation solve it?
- Preparation can almost solve it :: macro+85
- Preparation helps, but skill is still needed :: macro+50/micro+35

Q4B text: What execution skill is most important?
- Reaction and timing :: micro+80/mystiko+20
- Learning patterns :: micro+50/mystiko+50

Q4C text: What kind of alternative approach is it?
- Using the world/system: Physics, elements, traps, terrain, etc. :: mystiko+60/macro+40
- Using social or non-combat choices: Dialogue, disguise, stealth, quests, etc. :: mystiko+80

Q5 text: How much must players figure out enemy weaknesses?
- A lot: Attacks, patterns, weaknesses, or tricks must be learned. :: mystiko+75/micro+25
- Somewhat: Knowing weaknesses helps, but stats and equipment also matter. :: mystiko+65/macro+35
- A little: Enemies are mostly obvious and predictable. :: mystiko-30/macro+40
- Turn-based planning: Reading enemy options and deciding how to spend actions is central. :: mystiko+45/macro+55

Q6 text: How much does planning your character or team matter?
- It's the core of the game :: next=Q6A
- It's secondary :: next=Q6B

Q6A text: What kind of planning matters most?
- Team planning: Managing several characters and their abilities is the main challenge. :: macro+85/mystiko+15
- Character building: Skills, equipment, crafting, or upgrades are the main challenge. :: macro+85
- Switching tools/characters during play: Combining different abilities in real time matters. :: macro+60/micro+30

Q6B text: What matters most instead?
- Weapon feel and moves matter most :: micro+80
- Looks/roleplay matter more than numbers :: mystiko+50/micro+20

Q7 text: How much does where you are affect what happens?
- A lot: Terrain, height, cover, environmental effects, or chokepoints change the outcome. :: macro+70/mystiko+35
- A lot during action: Tight spaces, hazards, ledges, or movement make positioning difficult. :: micro+70/mystiko+20
- Very little: The ground and surroundings rarely change the outcome. :: macro-20/micro+20

Q8 text: How much does the game make players find their own way?
- Story/choice deduction: Players need to understand characters, choices, or consequences. :: mystiko+80/macro+20
- Exploration: Players need to notice clues, hidden paths, or discover where to go. :: mystiko+90
- Clear directions: Objectives are clearly marked and little figuring-out is needed. :: mystiko-30/macro+30

### Reward

Q9 text: What kind of progression reward matters most?
- Cosmetics/characters :: next=Q9A
- Power and better equipment :: next=Q9B

Q9A text: How are they obtained?
- Buy or randomly obtain them :: micro+70/macro+30
- Earn them through difficult content :: micro+60/mystiko+30
- Create/customize them yourself :: macro+45/mystiko+35

Q9B text: What kind of power progression is it?
- Bigger numbers: Better damage, stats, levels, equipment, etc. :: macro+80
- New abilities: Unlocking movement, exploration, or new ways to interact with the world. :: mystiko+70/macro+20

Q10 text: What gives the game its biggest sense of wonder?
- Big beautiful places :: mystiko+120
- Finding things nobody told you about :: mystiko+110/macro+20
- Becoming extremely powerful :: macro+60/micro+50
- Getting attached to characters :: mystiko+90

Q11 text: If your save disappeared, what would hurt to lose most?
- Build and resources :: macro+85
- Choices and world changes :: mystiko+90
- Characters/cosmetics :: next=Q11A

Q11A text: How was that collection assembled?
- Paid/saved-for collection :: micro+75/macro+30
- Earned through hard gameplay :: micro+80

Q12 text: How does the game provide status or prestige?
- High-level gear/achievements/leaderboards :: macro+90
- Beating other players :: micro+80/macro+15
- Having a rare/high-investment collection :: macro+80/micro+25
- No external status: Progress is mainly personal. :: mystiko+80

Q13 text: What becomes hardest when the player is tired?
- Reflexes and movement :: micro+80
- Reading and understanding :: next=Q13A
- Nothing much: The game remains comfortable to play. :: mystiko+90

Q13A text: What is hardest to read or manage when tired?
- Story/puzzles :: mystiko+75
- Managing systems/builds/resources :: macro+85

Q14 text: What produces the biggest payoff?
- Finally beating something through skill :: micro+90
- Making a clever build/setup work :: macro+85
- Finding a major secret :: mystiko+100
- Getting an extremely rare reward :: micro+65/macro+25

---

## Set C — Narrative

### Challenge

Q3 text: How much does physical skill matter for surviving?
- A lot: Aiming, dodging, movement, or fast reactions are important. :: micro+75
- Some: There are QTEs or occasional timing checks. :: micro+10/mystiko+40
- Little: Combat uses turns, menus, cards, or choices. :: micro-40/macro+30
- None: The game mainly asks the player to read, investigate, explore, or choose dialogue. :: micro-50

Q4 text: Does the game put pressure on time or resources?
- Yes :: next=Q4A
- No :: next=Q4B

Q4A text: What kind of pressure is it?
- Survival resources: Ammunition, health, crafting materials, money, etc. are scarce. :: macro+85/micro+25
- Limited time: Days, schedules, deadlines, or action points force difficult choices. :: macro+85
- Resources exist but are comfortable :: macro+25

Q4B text: Without time or resource pressure, how do players get past obstacles?
- Investigating clues is how players get past obstacles :: mystiko+85
- Understanding people/choices is the main challenge :: mystiko+45

Q5 text: When the game gives the player a mystery, what must they do?
- Read people: Detect lies, understand motives, or predict what someone will do. :: mystiko+85
- Predict combat: Learn attacks, weaknesses, or enemy patterns. :: mystiko+55/macro+35
- Study behaviour: Watch patrols, sound, sightlines, and timing. :: micro+45/macro+25/mystiko+15

Q6 text: What happens when the player makes a major mistake?
- The story permanently changes :: next=Q6A
- Game Over/checkpoint :: next=Q6B

Q6A text: What prevents the permanent change?
- Reading people and choices prevents it :: mystiko+90
- Fast reactions prevent it :: micro+30/mystiko+60

Q6B text: What usually causes the Game Over?
- Running out of supplies :: macro+50/micro+40
- Bad party/setup decisions :: macro+75/mystiko+15
- Bad physical execution :: micro+70

Q7 text: How can players gain an advantage before a confrontation?
- Stealth and positioning :: macro+45/micro+45
- Getting the first move by watching enemies and choosing the right moment :: macro+30/mystiko+30
- Investigating beforehand: Finding evidence, secrets, weaknesses, or useful information :: mystiko+90

Q8 text: Where is the game's deepest complexity?
- Story choices: Many decisions lead to different scenes, characters, or endings. :: mystiko+95
- Character/system building: Skills, equipment, abilities, or party choices interact deeply. :: macro+90
- Upgrading survival/combat tools :: macro+55/micro+35

### Reward

Q9 text: Does the game reward players with extra story or lore?
- Yes :: next=Q9A
- No :: next=Q9B

Q9A text: What kind of extra content is it?
- Art/audio extras: Galleries, music, cutscenes, models, etc. :: micro+85/macro+15
- World lore: Notes, recordings, books, environmental details, etc. :: mystiko+85
- Story branches: New scenes, paths, character fates, or endings. :: mystiko+60/macro+30

Q9B text: Without extra lore, what drives progression?
- Visible equipment upgrades :: micro+50/macro+30
- Changing relationships :: mystiko+65
- World exploration and discovery: Finding hidden areas, environmental details, or optional locations that expand the setting. :: mystiko+60/macro+20

Q10 text: What makes the game's big emotional payoff?
- A powerful ending or tragedy :: mystiko+110
- Solving the central mystery and reaching the true ending :: mystiko+80/macro+30
- Surviving something extremely difficult :: micro+60/macro+50

Q11 text: Does exploring the world reveal secret story content?
- Yes :: next=Q11A
- No :: next=Q11B

Q11A text: What kind of secret content is it?
- Secret bosses/content :: macro+75/mystiko+35
- Hidden story revelations :: mystiko+90
- Clues, codes, and hidden rooms :: mystiko+45/macro+45

Q11B text: Without secrets, what keeps the player engaged?
- Cinematic pacing and acting :: mystiko+60/micro+40
- Character relationships: Following character interactions, personal conflicts, and changing relationships keeps the player invested. :: mystiko+80
- The main story itself: Following the central plot, its major events, and how it unfolds keeps the player engaged. :: mystiko+75
- Player-driven choices: Deciding what to do or say and seeing those choices affect the journey keeps the player engaged. :: mystiko+60/macro+20

Q12 text: How important is 100% completion?
- Very important :: macro+85
- Nice extra :: macro+30/mystiko+45
- Not important :: mystiko+75

Q13 text: What does fatigue mainly make harder?
- Reflexes :: micro+80
- Understanding the story :: mystiko+85
- Managing systems :: macro+85

Q14 text: What best represents the game's lasting identity?
- Style and presentation :: micro+80/mystiko+20
- Ideas and moral questions :: mystiko+100
- Tense physical survival/gameplay :: macro+60/micro+30

---

## Set D — Challenge

### Challenge

Q3 text: When the player makes a mistake, how much does it hurt?
- Very heavily: One mistake can immediately lose a life, round, run, or fight. :: micro+90
- Heavily but recoverably: Mistakes hurt, but good positioning, defence, or resources can save the situation. :: micro+35/macro+45
- Mostly absorbed by strategy: A strong build, team, deck, or setup can compensate for mistakes. :: micro+10/macro+70
- Physical execution barely matters: The challenge mainly comes from decisions. :: micro-30

Q4 text: Does the player need preparation before acting?
- Yes :: next=Q4A
- No :: next=Q4B

Q4A text: How important is that preparation?
- Decisive: A bad build, draft, deck, economy, or setup can put the player in a losing position before execution begins. :: macro+80
- Important but recoverable: Good execution can overcome a bad setup. :: macro+30/micro+40
- Minor: Preparation exists but is not a major part of success. :: macro-20

Q4B text: Without preparation, what mostly decides success?
- Execution and positioning :: micro+70/mystiko+15/macro-40
- Resource decisions during the game :: macro+40/micro+30

Q5 text: How much does the player have to work with incomplete information?
- A lot: Sound, hidden enemies, fog, clues, or prediction are essential. :: mystiko+85
- Some: Scouting, vision, information gathering, or prediction matter. :: mystiko+60/macro+20
- Little: Enemies are usually visible and information is immediately available. :: mystiko+20/micro+40
- None: Everything important is visible. :: mystiko-30

Q6 text: How important is controlling space?
- Changing the environment: Destroying walls, opening paths, changing terrain, etc. :: next=Q6A
- Controlling fixed space: Zones, waves, traps, abilities, positioning, etc. :: next=Q6B

Q6A text: How central is changing the environment?
- Essential: Changing the environment is central to winning fights. :: mystiko+60/macro+40
- Occasional: It helps, but most fights happen in predictable spaces. :: macro+20/mystiko+15

Q6B text: How do players control fixed space?
- Abilities/units control space :: macro+60
- Precise utility/timing controls space :: micro+40/macro+20
- Direct positioning wins space :: micro+50

Q7 text: When there is a decisive clash, what usually determines the winner?
- Execution: Aim, reactions, combos, movement, timing. :: micro+90
- A mix of everything: Information, preparation, decisions, and execution all matter heavily. :: micro+35/macro+35/mystiko+35
- Team/system coordination: Ability combinations, cooldowns, positioning, roles, etc. :: macro+75/micro+15
- Numbers and setup: Better economy, build, cards, equipment, or scaling wins. :: macro+85

Q8 text: Does the game reward mind games or deception?
- Yes :: next=Q8A
- No :: next=Q8B

Q8A text: What kind of deception is it?
- Fakes and conditioning: Making opponents expect one thing and doing another. :: mystiko+70
- Baiting abilities/resources: Making the opponent waste something valuable before attacking. :: macro+60/mystiko+25

Q8B text: Without deception, what decides the outcome?
- Physical execution :: micro+60
- Resource/system advantage :: macro+40

### Reward

Q9 text: What gives the biggest high-stakes payoff?
- Pulling off an amazing clutch or difficult fight :: micro+90
- Outsmarting the opponent :: next=Q9A
- Executing a brilliant strategy/setup :: next=Q9B

Q9A text: What kind of outsmarting is it?
- Reading hidden information :: mystiko+85
- Setting up the situation beforehand :: macro+60/mystiko+25

Q9B text: How was that strategy executed?
- Team planning and coordination :: macro+80
- Adapting quickly during chaos :: macro+40/micro+30

Q10 text: What best shows a player's mastery?
- High rank :: macro+85
- Amazing mechanical plays :: micro+80
- Deep game knowledge: Knowing obscure mechanics, maps, timings, counters, etc. :: mystiko+60/macro+25
- Pure intensity: The game is rewarding mainly because every moment feels high-stakes. :: micro+30/mystiko+30

Q11 text: When watching top-level play, what is most impressive?
- Mechanical skill: Incredible reactions, combos, aim, movement, etc. :: micro+85
- Strategy: Drafts, compositions, resource plans, or coordinated tactics :: next=Q11A
- Mind games: Predictions, deception, traps, or clever reads :: mystiko+80

Q11A text: Do ordinary players copy professional strategies?
- Yes, heavily :: macro+85
- Rarely :: micro+35/macro+25

Q12 text: When the player is tired, what breaks down first?
- Physical execution :: micro+80
- Game sense :: mystiko+75 :: next=Q12A
- Strategic decisions :: macro+75 :: next=Q12B

Q12A text: Can raw skill compensate?
- Yes :: micro+40
- No :: mystiko+40

Q12B text: Can the player switch to a simpler/supporting role?
- Yes :: macro+50
- No :: micro+30/macro+20

Q13 text: Outside the actual match/run, what keeps players coming back?
- Cosmetics and trading :: micro+60/macro+20
- New characters/classes/cards :: macro+70/micro+20
- Mastery progression: Ranks, weapon mastery, achievements, account progression, etc. :: mystiko+35/macro+35

Q14 text: When players lose, what is usually the real reason?
- Bad strategy/team decisions :: macro+85
- The opponent was mechanically better :: micro+85
- They didn't see/read something :: mystiko+80
- The system was exploited or cheated :: micro+30/macro+30/mystiko+30
