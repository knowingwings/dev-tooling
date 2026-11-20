typedef struct { volatile unsigned ODR; } periph_t;
#define GPIOA ((periph_t *)0x40020000u)
void bsp_led_on(void);
void bsp_led_on(void) { GPIOA->ODR = 1u; }
