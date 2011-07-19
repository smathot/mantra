%module camera


%newobject camera;

%{
	extern unsigned int r, g, b;

	extern short match_mode;
	extern short scan_mode;
	extern short size_mode;
	extern int min_z;
	extern int track_x;
	extern int track_y;
	extern int track_z;
%}

extern unsigned int r, g, b;

extern short match_mode;
extern short scan_mode;
extern short size_mode;
extern int min_z;
extern int track_x;
extern int track_y;
extern int track_z;

void camera_init(char *device, int width, int height);
void camera_close(void);
void camera_capture(void);
void camera_get_px(short x, short y);
void camera_put_px(short x, short y);
void camera_save_frame(char *fname);
PyObject *camera_to_string(void);
int camera_get_control(int id);
void camera_set_control(int id, int value);
int camera_control_available(int id);
int camera_get_width(void);
int camera_get_height(void);

extern short match_at(int x, int y);
extern int color_match(int a, int b, int c, int d, int e, int f, int fuzziness);
void highlight_color(int color_r, int color_g, int color_b, int fuzziness);
extern void track_object(int color_r, int color_g, int color_b, int fuzziness, int pre_x, int pre_y, int highlight);
