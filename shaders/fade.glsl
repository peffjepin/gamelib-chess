#version 330

#vert
in vec2 v_pos;

void main()
{
    gl_Position = vec4(v_pos, 0, 1);
}

#frag

uniform float opacity;

void main()
{
    gl_FragColor = vec4(0, 0, 0, opacity);
}
