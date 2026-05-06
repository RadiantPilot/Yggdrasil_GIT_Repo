# Kinematikk — hvordan vet RPi hvilke vinkler servoane skal ha?

Her er en gjennomgang av hvordan styresystemet regner seg frem til riktige servovinkler ut fra en ønsket helning på toppplaten.

---

## Hva er en Stewart Platform?

Plattformen har to plater — en fast bunnplate og en bevegelig toppplate — koblet sammen med seks bein. Hvert bein har en servo som roterer en kort arm, og armspissen er koblet til toppplaten via et stag. Når servoen roterer, skyver eller trekker den toppplaten på sin side, og de seks servoane i fellesskap bestemmer hvilken helning toppplaten har.

Vår plattform bruker **kun rotasjon** — toppplaten holder seg alltid 120 mm over bunnplaten og vippes rundt midtpunktet.

Spørsmålet systemet må svare på til enhver tid:

> *Vi vil ha toppplaten i vinkel (roll, pitch, yaw) — hvilken vinkel skal hvert servo ha?*

---

## To typer kinematikk

**Fremover-kinematikk**: gitt servovinklene → hva er stillingen til toppplaten?

**Invers kinematikk (IK)**: gitt ønsket stilling → hva skal servovinklene være?

Vi bruker **invers kinematikk**. Vi vet hva vi vil, og regner bakover til vinklene som gir akkurat det.

---

## Geometrien — hva systemet vet på forhånd

Systemet kjenner plattformens mål som faste tall:

**Bunnplaten** (beveger seg aldri):
- 6 festepunkter på en sirkel med radius 100 mm
- Jevnt fordelt med 60° mellomrom: 0°, 60°, 120°, 180°, 240°, 300°

**Toppplaten**:
- 6 festepunkter på en sirkel med radius 75 mm
- Samme fordeling, men 30° forskjøvet fra bunnplaten: 30°, 90°, 150°, 210°, 270°, 330°

**Hvert bein**:
- Servoarm: **a = 25 mm** — roteres av servoen
- Stag: **s = 150 mm** — kobler armspissen til toppplaten

```
     Toppplate
    o---[stag]---o
   /               \
[arm]             [arm]
  |                 |
[servo]          [servo]
       Bunnplate
```

---

## Fra ønsket helning til servovinkler — fire steg

### Steg 1: Roter toppplatens festepunkter

Ønsket stilling oppgis som tre vinkler:
- **Roll** — vipping til siden (som å helle et glass)
- **Pitch** — vipping forover/bakover
- **Yaw** — rotasjon rundt opp-aksen

Disse tre slås sammen til én rotasjonsmatrise `R` (yaw → pitch → roll):

```
R = Rz(yaw) · Ry(pitch) · Rx(roll)
```

`R` brukes på hvert av toppplatens 6 festepunkter, som deretter løftes opp til hvilehøyden:

```
P_verden[i] = R · P_lokal[i] + [0, 0, 120]
```

Nå vet vi nøyaktig hvor hvert festepunkt på toppplaten er i rommet, gitt den ønskede helningen.

### Steg 2: Beregn beinvektorene

For hvert av de 6 beinene: trekk fra bunnfestepunktet:

```
L[i] = P_verden[i] - B[i]
```

`L[i]` er en 3D-vektor som sier "i denne retningen og denne lengden må beinet strekke seg". Det er disse vektorene som sendes videre til selve kinematikk-beregningen.

### Steg 3: Finn servovinkel fra beinvektor

Dette er kjernen. For hvert bein gjøres tre delsteg:

**3a. Projisér inn i servoens plan**

Hvert servo roterer i ett bestemt vertikalt plan, gitt av servomontasjevinkelen `m`. Vi trenger bare beinvektorens bidrag i dette planet:

```
L_r = L_x · cos(m) + L_y · sin(m)    ← horisontal retning i servoplanet
L_z = L_z                             ← vertikal (uendret)
```

**3b. Sett opp geometriligningen**

Servoarmen peker ut fra aksen i vinkel `α` (0° = rett ned, 90° = horisontal, 180° = rett opp). For at staget (150 mm) akkurat skal nå toppfestepunktet, må denne ligningen stemme:

```
L_r · sin(α) − L_z · cos(α) = M

der M = (d² + a² − s²) / (2a)
    d = total lengde på beinvektoren
    a = servoarmlengde (25 mm)
    s = staglengde (150 mm)
```

**3c. Løs for `α`**

Venstresiden kan skrives om ved å bruke en hjelpevinkel `δ`:

```
R = √(L_r² + L_z²)
δ = atan2(L_z, L_r)

→  R · sin(α − δ) = M

→  α = δ + arcsin(M / R)
```

`α` er servovinkelen. Den klipper vi til servoens mekaniske grenser (`min_angle_deg`…`max_angle_deg`) og sender videre.

### Steg 4: Hva skjer når stillingen er umulig?

Hvis `|M / R| > 1` finnes det ingen gyldig vinkel — toppplaten er bedt om en helning som er for ekstrem for beinet å håndtere.

I stedet for å krasje gjør systemet dette:
1. Merker hvilke servoer som ikke kan løses (`last_clamped_mask`)
2. Returnerer de **siste gyldige servovinklene** (`_last_valid_angles`)
3. Servoene blir stående — plattformen beveger seg ikke videre

GUI og kontroller kan lese `last_solve_clamped` for å se om siste beregning ble fryst. For å teste om en stilling er mulig uten å faktisk sende noe til servoene, bruk `is_pose_reachable_exact()`.

---

## Parametertabell

Alle verdier fra `config/default_config.yaml`.

| Symbol | Beskrivelse | Verdi |
|--------|-------------|-------|
| R_base | Bunnplatens festepunkt-radius | 100 mm |
| R_top | Toppplatens festepunkt-radius | 75 mm |
| a | Servoarmlengde | 25 mm |
| s | Staglengde | 150 mm |
| h | Hvilehøyde (Z-høyde for toppplaten) | 120 mm |
| B_i | Bunnfestepunktvinkler | 0°, 60°, 120°, 180°, 240°, 300° |
| P_i | Toppfestepunktvinkler | 30°, 90°, 150°, 210°, 270°, 330° |
| α_i | Servovinkel for bein i | 0° (ned) → 90° (horisontalt) → 180° (opp) |

---

## Kode-referanser

| Konsept | Fil |
|---------|-----|
| Rotasjonsmatrise og beinvektorer | `stewart_platform/geometry/platform_geometry.py` |
| Kjernealgoritmen (steg 3) | `stewart_platform/kinematics/inverse_kinematics.py` — `_leg_length_to_servo_angle()` |
| Frys-mekanismen | `inverse_kinematics.py` — `solve()` |
| Pose-datastruktur (roll/pitch/yaw) | `stewart_platform/geometry/pose.py` |
| Geometriparametere | `config/default_config.yaml` |
