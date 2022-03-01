#version 330

#define WHITE vec3(0.97, 0.88, 0.88)
#define BLACK vec3(0.23, 0.23, 0.32)
#define TINT vec4(0.95, 0.1, 0.1, 0.35)

#vert
// vertices
in vec3 v_pos;
in vec3 v_norm;

// instanced
in mat4 model;
in int player;
in int entity;

uniform mat4 proj;
uniform mat4 view;
uniform int selected;

out vec3 f_pos;
out vec3 f_norm;
out vec3 f_color;
out vec4 f_tint;

void main()
{
    vec4 world_space_normal = model * vec4(v_norm, 0.0);
    vec4 world_space_vertex = model * vec4(v_pos, 1.0);

    f_norm = normalize(world_space_normal.xyz);
    f_pos = world_space_vertex.xyz;

    if (player == 0)
        f_color = BLACK;
    else
        f_color = WHITE;

    if (selected == entity)
        f_tint = TINT;
    else
        f_tint = vec4(0);

    gl_Position = proj * view * world_space_vertex;
}

#frag

#include <lighting.glsl>

in vec3 f_pos;
in vec3 f_norm;
in vec3 f_color;
in vec4 f_tint;

void main()
{
    vec3 lighting_color = calculate_lighting(f_norm, f_pos);
    vec3 actual_color = lighting_color * f_color;

    gl_FragColor = vec4(actual_color, 1.0);
    gl_FragColor.rgb = mix(gl_FragColor.rgb, f_tint.rgb, f_tint.a);
}

