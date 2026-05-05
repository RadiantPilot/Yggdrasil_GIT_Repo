# Kinematikk og styring av Stewart-plattformen

Dette dokumentet beskriver det matematiske grunnlaget for hvordan plattformen beregner servovinkler fra en ønsket orientering.

---

## 1. Plattformens oppbygging

En Stewart-plattform består av to plater forbundet med seks bein. Bunnplaten er fast, mens toppplaten kan beveges ved å endre lengden på hvert bein.

I denne implementasjonen er beinlengden ikke direkte justerbar. I stedet har hvert bein et servohorn som kobler til bunnplaten, og et forbindelsesstag som kobler hornets ytterpunkt til et ledd på toppplaten. Når servoen roterer, endres hornspissens posisjon, og staget presser eller trekker toppplaten i ønsket retning.

Plattformen styres kun rotasjonelt. Toppplaten holdes på en fast hvilehøyde og kan vippes rundt sentrum.

---

## 2. Koordinatsystem og geometri

Alle koordinater er i millimeter. Origo er midt på bunnplaten.

**Bunnplaten** har seks leddpunkter plassert på en sirkel med radius $r_b$, jevnt fordelt med 60 graders mellomrom:

> Fiks tallene (De stemmer ikke med plattformen)
$$B_i = \bigl(r_b \cos\theta_i,\ r_b \sin\theta_i,\ 0\bigr), \quad \theta_i \in \{0°, 60°, 120°, 180°, 240°, 300°\}$$

**Toppplaten** har tilsvarende seks leddpunkter på en sirkel med radius $r_p$, forskjøvet med 30 grader relativt til bunnplatens vinkler:

$$P_i^{\text{lok}} = \bigl(r_p \cos\phi_i,\ r_p \sin\phi_i,\ 0\bigr), \quad \phi_i \in \{30°, 90°, 150°, 210°, 270°, 330°\}$$

I standardkonfigurasjon er $r_b = 100$ mm, $r_p = 75$ mm, $a = 25$ mm, $s = 150$ mm og $h = 120$ mm.

---

## 3. Fra ønsket orientering til verdenskoordinater

Toppplatens orientering beskrives med tre Euler-vinkler: roll ($\alpha$), pitch ($\beta$) og yaw ($\gamma$), alle i grader. Disse definerer en rotasjonsmatrise $R$ etter ZYX-konvensjonen:

$$R = R_z(\gamma) \cdot R_y(\beta) \cdot R_x(\alpha)$$

For å finne toppplatens leddpunkter i verdenskoordinater roteres de lokale posisjonene og legges til en fast translasjon langs z-aksen:

$$P_i^{\text{verden}} = R \cdot P_i^{\text{lok}} + \begin{pmatrix} 0 \\ 0 \\ h \end{pmatrix}$$

---

## 4. Invers kinematikk: fra beinvektor til servovinkel

Beinvektoren for bein $i$ er forskjellen mellom toppplatens og bunnplatens ledd i verdenskoordinater:

$$\vec{L}_i = P_i^{\text{verden}} - B_i$$

Målet er å finne servovinkelen $\alpha_i$ slik at hornspissens avstand til toppplateddet blir lik staglengden $s$.

### 4.1 Dekomponering i servoplanet

Servohornet roterer i et vertikalt plan definert av monteringsvinkelen $m_i$. Beinvektoren deles opp i to retninger:

$$L_r = L_x \cos m_i + L_y \sin m_i \qquad \text{(horisontal i servoplanet)}$$
$$L_z \qquad \text{(vertikal)}$$

### 4.2 Geometrisk krav

Hornspissens posisjon relativt til bunnleddet er:

$$\text{hornspiss} = \bigl(a\sin\alpha \cos m_i,\ a\sin\alpha \sin m_i,\ {-a\cos\alpha}\bigr)$$

Kravet om at staget skal nå toppplateddet gir $|\text{hornspiss} - \vec{L}_i|^2 = s^2$, som etter utregning forenkles til:

$$L_r \sin\alpha - L_z \cos\alpha = M, \qquad M = \frac{d^2 + a^2 - s^2}{2a}$$

### 4.3 Løsning

Venstresiden skrives om ved hjelp av en hjelpevinkel:

$$R = \sqrt{L_r^2 + L_z^2}, \qquad \delta = \arctan\!\Bigl(\frac{L_z}{L_r}\Bigr)$$

Dette gir $R \sin(\alpha - \delta) = M$, og dermed:

$$\alpha = \delta + \arcsin\!\Bigl(\frac{M}{R}\Bigr)$$

Hvis $|M/R| > 1$ er den ønskede posen utenfor det fysisk mulige. I så fall fryses servoene på siste gyldige vinkel, og plattformen beveger seg ikke videre i den retningen.

---

## 5. Grenser og sikkerhet

Når servovinkelen er beregnet, begrenses den til det mekaniske arbeidsområdet $[\alpha_{\min},\ \alpha_{\max}]$. I tillegg kontrollerer systemet at:

- Rotasjonen ikke overstiger 30 grader fra nøytralt
- Vinkelhastigheten ikke overstiger 60 grader per sekund
- IMU-akselerometeret ikke registrerer verdier over 4 g

---

## 6. Symboloversikt

| Symbol | Betydning | Standardverdi |
|--------|-----------|---------------|
| $r_b$ | Bunnplatens leddradius | 100 mm |
| $r_p$ | Toppplatens leddradius | 75 mm |
| $a$ | Servohormlengde | 25 mm |
| $s$ | Staglengde | 150 mm |
| $h$ | Hvilehøyde | 120 mm |
| $\alpha, \beta, \gamma$ | Roll, pitch, yaw | $\leq$ 30° |
| $\alpha_i$ | Servovinkel for bein $i$ | 0° til 180° |
