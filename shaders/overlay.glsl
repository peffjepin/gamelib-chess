#version 330

#define HEIGHT 0.1
#define STD_ALPHA 0.65
#define HOVERED_ALPHA 0.8
#define LAST_MOVE vec3(0.6, 0.45, 0.3)
#define CAPTURE vec3(0.78, 0.4, 0.4)
#define REGULAR vec3(0.38, 0.4, 0.75)

#vert

// 0 - 1 quad
in vec3 v_pos;

// rank and file
in ivec2 i_board;
in int i_capture;

uniform ivec2 hovered;
uniform ivec2 prev_move;
uniform mat4 view;
uniform mat4 proj;

out vec4 f_color;
out vec3 f_pos;

void main()
{
    float alpha;
    float height;
    float color_scale;
    if (i_board == hovered)
    {
        alpha = HOVERED_ALPHA;
        height = HEIGHT / 3;
        color_scale = 1;
    }
    else
    {
        alpha = STD_ALPHA;
        height = HEIGHT;
        color_scale = 0.8;
    }

    if (i_capture == 1)
        f_color = color_scale * vec4(CAPTURE, alpha);
    else if (prev_move == i_board)
        f_color = vec4(LAST_MOVE, STD_ALPHA);
    else
        f_color = color_scale * vec4(REGULAR, alpha);

    f_pos = v_pos;
    gl_Position = proj * view * vec4((v_pos - 0.5).xy + i_board, height, 1);
}

#frag
#include <lighting.glsl>

in vec3 f_pos;
in vec4 f_color;

void main()
{
    vec3 lighting = calculate_lighting(vec3(0, 0, 1), f_pos);
    gl_FragColor = vec4(f_color.rgb * lighting, f_color.a);
}

