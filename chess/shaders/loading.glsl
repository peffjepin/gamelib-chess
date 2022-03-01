#version 330

#vert 
#define HEIGHT 0.05
#define RANGE 0.2

in vec2 v_pos;

uniform float time;

void main() 
{
    float off;
    float t = sin(time);
    float diff = abs(v_pos.x - t);

    if (diff < RANGE)
        off = HEIGHT * (RANGE - diff) / RANGE;
    else
        off = 0;

    gl_Position = vec4(v_pos.x, v_pos.y + off, 0, 1);
} 

#frag
void main()
{
    gl_FragColor = vec4(1);
}
