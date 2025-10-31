#include <stdio.h>
#include <math.h>

/**
 * @brief Calcula a média final das disciplinas AVAS.
 * * Fórmula: (NP1 * 4 + NP2 * 4 + PIM * 2) / 10
 * * @param np1 Nota da NP1 (float).
 * @param np2 Nota da NP2 (float).
 * @param pim_nota Nota do PIM (float).
 * @return float A média final calculada (arredondada para 2 casas decimais).
 */
float calculate_final_media(float np1, float np2, float pim_nota) {
    float media = (np1 * 4.0f + np2 * 4.0f + pim_nota * 2.0f) / 10.0f;
    
    // Arredonda para duas casas decimais (padrão C)
    // O Python irá arredondar novamente na função de suporte para garantir
    return roundf(media * 100.0f) / 100.0f;
}