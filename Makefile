CC      = m68k-elf-gcc
OBJCOPY = m68k-elf-objcopy
CFLAGS  = -m68000 -O2 -Wall -fomit-frame-pointer -ffreestanding -fno-builtin \
          -fno-tree-loop-distribute-patterns -nostdlib
ROM     = build/ancient_wars.bin

all: $(ROM)

src/gfx.h: tools/gfx.py
	python3 tools/gfx.py

src/music.h: tools/music.py
	python3 tools/music.py

build/game.elf: src/boot.s src/main.c src/sound.c src/md.h src/sound.h src/gfx.h src/music.h md.ld
	@mkdir -p build
	$(CC) $(CFLAGS) -T md.ld -Wl,-Map=build/game.map -o $@ src/boot.s src/main.c src/sound.c -lgcc

$(ROM): build/game.elf
	$(OBJCOPY) -O binary $< $@
	python3 tools/fixrom.py $@

run: $(ROM)
	blastem $(ROM)

preview: tools/gfx.py
	PREVIEW=1 python3 tools/gfx.py

clean:
	rm -rf build src/gfx.h src/music.h

.PHONY: all run preview clean
