# Bar venue — ground floor plan (Hong Kong)

A to-scale architectural floor plan for a bar in a **12.0 m × 8.0 m** rectangular
ground-floor tenancy, drawn as a single A0 sheet at **1:20**, annotated for
Buildings Department (BD), Fire Services Department (FSD) and Liquor Licensing
Board review.

| File | What it is |
| --- | --- |
| `bar-floor-plan-1-20.svg` | The drawing. Vector, prints at A0 (1189 × 841 mm) at 1:20. |
| `bar-floor-plan-1-20.png` | Raster export, 4756 px wide (≈ 100 dpi at A0). |
| `generate_plan.py` | Generator. Everything on the sheet is computed from the geometry constants at the top. |

Regenerate with:

```
python3 generate_plan.py bar-floor-plan-1-20.svg
```

The script prints the derived areas, occupant capacity and seat counts so the
numbers on the sheet and the numbers in this README cannot drift apart.

> **The brief left the dimensions as a placeholder** (`[insert dimensions e.g.
> 12m × 8m]`), so the example figure — 12 m × 8 m internal, 96.0 m² — was used
> throughout. See [Changing the dimensions](#changing-the-dimensions).

---

## What is on the sheet

* **Plan at 1:20** with dimension lines, a north arrow and a scale bar.
* **Section A–A at 1:25** through EXIT 1, the circulation spine and the toilet
  lobby — this is what demonstrates the 2000 mm minimum headroom, which a plan
  cannot show.
* **Schedules**: occupant capacity, seating and standing, key clear dimensions,
  means-of-escape compliance check, fire service installations, travel
  distances, exits and escape routes, fire resisting construction, sanitary
  fitments, assumptions.
* **Legend**, general/statutory/operational notes, references, revisions and a
  title block.

## Layout

| Zone | Provision |
| --- | --- |
| Front bar counter | 4500 run + 1350 return, 600 deep, back-bar shelving 350 deep |
| Bartender working zone | **1000 mm clear** (900 mm minimum required) |
| Bar stools | 9 (7 at the run, 2 at the return) |
| Table seating | 4 banquette bays × 4 = **16 seats** |
| Lounge seating | 2 clusters = **8 seats** |
| **Total seats** | **33** |
| Standing areas | 6.1 m² net @ 0.5 m²/person = **12 persons** |
| Designated liquor-consumption area | **53.0 m²**, demarcated by the chain-dashed magenta boundary |
| Back of house | Cellar / liquor store, glasswash / servery, staff room + lockers |
| Toilets | Accessible unisex WC (Ø1500 turning circle), WC (F), WC (M) with urinal |

Total design population: 33 seated + 12 standing + 5 staff = **50 persons**.

## Means of escape

Designed to the *Code of Practice for Fire Safety in Buildings 2011* (BD),
Part B.

| Item | Required | Provided |
| --- | --- | --- |
| Number of exits | 2 | 2 |
| Separation of exits | remote | 12.0 m apart (> ½ diagonal, 7.5 m) |
| Exit route clear width | 1050 mm | 1200 – 1400 mm |
| EXIT 1 clear door width | 750 mm | 1700 mm (2 No. 900 leaves) |
| EXIT 2 clear door width | 750 mm | 1130 mm |
| Aggregate clear exit width | 1050 mm | 2830 mm |
| Widest exit discounted | 1050 mm | 1130 mm |
| Longest travel distance | 24 m | 8.6 m |
| Longest single-direction travel | 18 m | 5.0 m |
| Clear headroom on escape routes | 2000 mm | 2600 mm (2400 mm under the bulkhead) |
| Doors open in the direction of escape | required | both exits |
| Openable from inside without a key | required | panic bolt / lever |

* **EXIT 1** — main entrance, south wall, direct to the public street.
* **EXIT 2** — rear final exit through a protected corridor (1300 mm clear,
  FRR −/60/60) to the common rear corridor and protected staircase.
* Escape routes are hatched green on the sheet and carry no furniture.
* Where two routes subtend less than 45° at the point of origin, that part of
  the floor is treated as single-direction escape; the longest such travel is
  5.0 m, from the east end of the toilet lobby to the divergence at spine A.

## Occupant capacity

Calculated by the Table B1 method of CoP 2011:

| Accommodation | Area m² | m²/person | Persons |
| --- | ---: | ---: | ---: |
| Public drinking / seating area (net) | 49.45 | 1 | 50 |
| Bar servery | 8.78 | 7 | 2 |
| Glasswash / servery | 5.00 | 7 | 1 |
| Cellar / liquor store | 5.50 | 30 | 1 |
| Staff room / BOH lobby | 3.50 | 9 | 1 |
| **Total** | | | **55** |

Exit provision is designed for **60 persons**.

## Fire service installations

8 illuminated exit signs (including directional), 17 emergency light fittings
(2 hour duration), 2 × water 9 L and 2 × CO₂ 2 kg extinguishers, 1 fire
blanket, a manual call point and a sounder at each exit, 10 smoke and 2 heat
detectors, and 12 indicative sprinkler heads. The building hose reel in the
common corridor is shown as existing, by others.

---

## Caveats — please read before using this

* **This is a design study, not a submission drawing.** Plans for building
  works, means of escape and fire service installations have to be prepared and
  certified by an Authorized Person / Registered Structural Engineer and a
  Registered Fire Service Installation Contractor, and approved by BD and FSD,
  before any work is carried out or any licence is granted.
* The **"required" figures** in the compliance check are the design targets set
  in the brief together with the values normally applied to this use class. The
  governing table in CoP 2011, and the sprinklered / unsprinklered basis, must
  be confirmed by the Authorized Person.
* The building is **assumed to be sprinkler protected**. If it is not, travel
  distances and the permitted occupant capacity must be re-assessed — FSD
  applies more restrictive margins to unsprinklered premises.
* **Ground / street level is assumed.** Upper-floor and basement premises
  attract more onerous requirements: discharge through a protected staircase,
  shorter travel distances and a lower permitted capacity.
* **Sanitary fitment numbers are indicative** and must be verified against the
  Building (Standards of Sanitary Fitments, Plumbing, Drainage Works and
  Latrines) Regulations, Cap. 123I, for the assessed capacity.
* No cooking, and no live entertainment or dancing, is assumed. Either would
  change both the licence and the fire service requirements.

---

## Changing the dimensions

`ROOM_W` and `ROOM_H` at the top of `generate_plan.py` drive the walls, the
overall dimension chains, the area calculations and the title block. Changing
them alone will move the shell but **will not re-plan the interior** — the zone
rectangles (bar, seating, spines, BOH rooms) are hand-tuned coordinates in the
same block of constants and have to be re-tuned with the shell. The
compliance schedules recompute automatically from whatever geometry is in
place, so a re-tune is verifiable: run the script and read the printed areas,
capacity and seat counts.

The derived figures the script prints on every run:

```
public area (net) · licensed area · standing area and persons ·
occupant capacity · seats by type · design population
```

## References

* Code of Practice for Fire Safety in Buildings 2011 — Buildings Department
  (Part B: Means of Escape; Part C: Fire Resisting Construction)
* Codes of Practice for Minimum Fire Service Installations and Equipment —
  Fire Services Department
* Design Manual: Barrier Free Access 2008 — Buildings Department
* Dutiable Commodities (Liquor) Regulations, Cap. 109B
* Building (Standards of Sanitary Fitments, Plumbing, Drainage Works and
  Latrines) Regulations, Cap. 123I
* Places of Public Entertainment Ordinance, Cap. 172 · Smoking (Public Health)
  Ordinance, Cap. 371
