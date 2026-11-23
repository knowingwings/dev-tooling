#include <stdlib.h>
#include <stdio.h>
typedef struct { volatile unsigned ISR; volatile unsigned ODR; } periph_t;
#define USART1 ((periph_t *)0x40013800u)
#define GPIOA ((periph_t *)0x40020000u)
void HAL_Delay(unsigned ms);
void motor_step(void);
void motor_step(void)
{
    char buf[16];
    double gain = 1.5;
    GPIOA->ODR = 1u;
    while (!(USART1->ISR & 0x80u));
    HAL_Delay(10);
    sprintf(buf, "%d", (int)gain);
    void *p = malloc(10);
    free(p);
    do { gain -= 1.0; } while (gain > 0.0);
}
void __NOP(void);
unsigned HAL_GetTick(void);
void motor_wait(void);
void motor_wait(void)
{
    while (!(USART1->ISR & 0x40U))
        ;
    while (!(USART1->ISR & 0x20U)) {
        __NOP();
    }
    const unsigned t0 = HAL_GetTick();
    while (!(USART1->ISR & 0x10U) && HAL_GetTick() - t0 < 10U) {
    }
}
