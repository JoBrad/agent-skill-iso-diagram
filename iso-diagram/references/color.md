# Color

## Default palette

Tuned from the Okabe-Ito palette, which is designed to be color blind accessible. Values live in `themes/default.json`; `iso-palette default -o OUT.svg`
draws the swatch sheet.

| Slot | Stroke | Text shade | Notes |
| --- | --- | --- | --- |
| 1 blue | `#3478C8` | `#215EA3` | |
| 2 vermillion | `#E26D33` | `#B44F1C` | |
| 3 green | `#17A07A` | `#0C7558` | |
| 4 rose | `#CC74AE` | `#A04E85` | |
| 5 amber | `#E5A93A` | `#8A6410` | light: outlines use the text shade |
| 6 sky | `#68BDEA` | `#2B6F98` | light: outlines use the text shade; also the flow color |
| leaf neutral | `#6B7280` | `#374151` | always the deepest level |

Each slot gets two tints mixed toward white: the top face at 89%, the side at 62%.

## Encoding

- Pick one encoding per diagram, for the story: by level (default), kind, status, or owner.
  Hold it across the diagram and across a set telling the same kind of story.
- By level: slots in order from the top level; the deepest level takes neutral. Adjacent
  levels then get the most different colors.
- A node's `slot` overrides the encoding. Use it rarely, and say why.
- Flows and pipes use the flow slot (sky), so traffic reads the same in both styles.
- Emphasize by muting the rest, not by recoloring what matters.

## Accessibility

- Color is never the only cue: every color comes with a label, and every flow with
  arrowheads, chevrons, or numbers.
- Text uses a slot's text shade (all at least 5:1 on white). Large titles (24px and up) may
  use the stroke, which passes the 3:1 large-text minimum except for the light slots.
- Lines need 3:1 against white. Amber and sky strokes are about 2:1, so their outlines use
  the text shade; their fills keep the hue.
- Under simulated color blindness the closest stroke pairs are vermillion and amber
  (deuteranopia, 14.4), rose and neutral (protanopia, 17.0), and blue and green
  (tritanopia, 16.8). Slot order keeps those pairs apart in most diagrams. Any new palette
  should keep every pair at 15 or more; `palette.py` prints the closest pair per type.
