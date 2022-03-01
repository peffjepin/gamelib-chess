#version 330

#vert
in vec3 v_pos;

uniform mat4 view;
uniform mat4 proj;

out vec3 f_pos;

void main()
{
    f_pos = v_pos;
    gl_Position = proj * view * vec4(v_pos, 1);
}


#frag
#include <lighting.glsl>

#define WHITE vec3(0.78, 0.7, 0.7)
#define BLACK vec3(0.25, 0.25, 0.3)
#define EDGE vec3(0.5, 0.45, 0.55)
#define BOARD_UV_MULT 0.35
#define EDGE_UV_MULT 0.35

in vec3 f_pos;

uniform sampler2D marble;
uniform sampler2D wood;

void main()
{
    vec3 normal = normalize(cross(dFdx(f_pos), dFdy(f_pos)));
    vec3 lighting = calculate_lighting(normal, f_pos);
    ivec2 tile = ivec2(floor(f_pos.xy - 0.5));

    if (f_pos.z < 0)
    {
        vec3 tex = texture(wood, f_pos.xy * EDGE_UV_MULT).rgb;
        gl_FragColor = vec4(lighting * EDGE * tex, 1.0);
    }
    else if (tile.x > 7 || tile.x < 0 || tile.y > 7 || tile.y < 0)
    {
        vec3 tex = texture(wood, f_pos.xy * EDGE_UV_MULT).rgb;
        gl_FragColor = vec4(lighting * EDGE * tex, 1.0);
    }
    else if ((tile.x + tile.y) % 2 == 0)
    {
        // black tile
        vec3 tex = texture(marble, f_pos.xy * BOARD_UV_MULT).rgb;
        gl_FragColor = vec4(lighting * BLACK * tex, 1.0);
    }
    else
    {
        // white tile
        vec3 tex = texture(marble, f_pos.xy * BOARD_UV_MULT).rgb;
        gl_FragColor = vec4(lighting * WHITE * tex, 1.0);
    }
}
