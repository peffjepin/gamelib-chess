vec3 light_color = vec3(0.92, 0.92, 0.99);
vec3 light_pos = vec3(3.5, 3.5, 20.0);
float ambient_strength = 0.25;

vec3 calculate_lighting(vec3 normal, vec3 world_pos)
{
    vec3 light_dir = normalize(light_pos - world_pos);
    float diffuse_strength = max(dot(normal, light_dir), 0.0);
    vec3 diffuse = diffuse_strength * light_color;
    vec3 ambient = light_color * ambient_strength;
    return ambient + diffuse;
}

