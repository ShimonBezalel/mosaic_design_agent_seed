# Tile Compile Demo Notes

- The editable area is the left 280 by 200 pixels. The gray right strip is excluded by opaque mask alpha.
- Four broad source regions match Terracotta, Deep Blue, Turquoise, and Olive Green.
- A 3 by 3 Sun Yellow island tests low-demand color removal and tiny-region cleanup.
- Compile with `max_colors=4`, coarse granularity, and a minimum region area of 120 pixels.
- The final map should use three to four palette colors, never colors outside this palette.
- Generated maps are planning aids. They are not construction-ready without artist review.
