# Define variables
MPY_CROSS = ../micropython/mpy-cross/build/mpy-cross

SRC_DIR = lib
OUT_DIR = 1.x/lib
SRC = $(wildcard $(SRC_DIR)/*.py)
OUT = $(patsubst $(SRC_DIR)/%.py, $(OUT_DIR)/%.mpy, $(SRC))

# Default target
all: $(OUT)

# Rule to create .mpy from .py
$(OUT_DIR)/%.mpy: $(SRC_DIR)/%.py
	$(MPY_CROSS) $< -o $@

# Clean up
clean:
	rm -f $(OUT)

# Phony targets
.PHONY: all clean

