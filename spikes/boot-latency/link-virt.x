/* QEMU aarch64 `virt`: RAM starts at 0x4000_0000; the DTB is placed at its base. */
ENTRY(_start)
SECTIONS
{
  . = 0x40080000;
  .text : { KEEP(*(.text._start)) *(.text .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  .data : { *(.data .data.*) }
  .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) }
  . = ALIGN(16);
  . = . + 0x10000;
  __stack_top = .;
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
