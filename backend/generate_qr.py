import generate_qr

codes = [
    "BSH-01", "BSH-02",
    "BRG-01", "BRG-02",
    "BKT-01", "BKT-02",
    "RTR-01", "RTR-02", "RTR-03", "RTR-04"
]

for code in codes:
    img = generate_qr.make(code)
    img.save(f"{code}.png")
    print(f"Generated {code}.png")