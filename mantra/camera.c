#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <libv4l2.h>
#include <linux/videodev2.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/time.h>
#include <Python.h>

#define MIN(a,b) ((a)>(b)?(b):(a))
#define MAX(a,b) ((a)<(b)?(b):(a))

// Determines the maximum resolution of the webcam
#define MAX_RES_X		1280
#define MAX_RES_Y		1024

// How many pixels should be skipped while scanning the image for the first time
#define SCAN_ACCURACY	4

// Some constants
#define MATCH_ABS		0
#define MATCH_REL		1
#define SIZE_SURFACE	0
#define SIZE_WIDTH		1
#define SCAN_BLOCK		0
#define SCAN_SPIRAL		1

// Some global variables
short match_mode = MATCH_REL;
short size_mode = SIZE_WIDTH;
short scan_mode = SCAN_SPIRAL;
int min_z = 50;

// These variables are used to communicate the tracking to Etracker
int track_x = -1;
int track_y = -1;
int track_z = 0;

// This array holds information about matching pixels in the image
short match[MAX_RES_X][MAX_RES_Y];

// Holds information tracking of an object
typedef struct {
	short keep_scanning;
	double x;
	double y;
	int count;
} SCAN;

// A v4l2 buffers
struct buffer {
	void *start;
	size_t length;
};

// The nr of buffers available to v4l2
const int NR_OF_BUFFERS = 2;

int camera_fd;
struct buffer *buffers;
unsigned char *frame;
int bytesperpx;
struct v4l2_format format;
unsigned int r, g, b;

void camera_open(char *device)
{
	extern int camera_fd;
	
	camera_fd = v4l2_open(device, O_RDWR);
}

void camera_set_format(int width, int height)
{
	extern struct v4l2_format format;
	extern unsigned char *frame;	
	extern int camera_fd;
	extern int bytesperpx;
	
	format.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	format.fmt.pix.width = width;
	format.fmt.pix.height = height;
	format.fmt.pix.pixelformat = V4L2_PIX_FMT_RGB24;
	format.fmt.pix.field = V4L2_FIELD_INTERLACED;

	if(v4l2_ioctl(camera_fd, VIDIOC_S_FMT, &format)) {
	  printf("Error in VIDIOC_S_FMT\n");
	}

	frame = malloc(format.fmt.pix.sizeimage);
	bytesperpx = format.fmt.pix.bytesperline / format.fmt.pix.width;
}

int camera_get_width(void)
{
	extern struct v4l2_format format;

	return format.fmt.pix.width;
}

int camera_get_height(void)
{
	extern struct v4l2_format format;

	return format.fmt.pix.height;
}

void camera_init_buffers(void)
{
	extern struct buffer *buffers;	
	struct v4l2_requestbuffers reqbuf;
	extern int camera_fd;
	int i;
	
	reqbuf.count = NR_OF_BUFFERS;
	reqbuf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	reqbuf.memory = V4L2_MEMORY_MMAP;
	if (v4l2_ioctl(camera_fd, VIDIOC_REQBUFS, &reqbuf)) {
		printf("Error in VIDIOC_REQBUFS\n");
	};
		
	buffers = malloc(reqbuf.count * sizeof(struct buffer));

	for (i = 0; i < NR_OF_BUFFERS; i++) {
		struct v4l2_buffer buffer;
		buffer.index = i;
		buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
		buffer.memory = V4L2_MEMORY_MMAP;

		if (v4l2_ioctl(camera_fd, VIDIOC_QUERYBUF, &buffer)) {
			printf("Error in VIDIOC_QUERYBUF\n");
		}

		buffers[i].length = buffer.length;
		buffers[i].start = v4l2_mmap(NULL, buffer.length,
			PROT_READ | PROT_WRITE, MAP_SHARED,
			camera_fd, buffer.m.offset);    
	}

	for (i = 0; i < NR_OF_BUFFERS; i++) {
		struct v4l2_buffer buffer;
		buffer.index = i;
		buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
		buffer.memory = V4L2_MEMORY_MMAP;
		
		if (v4l2_ioctl(camera_fd, VIDIOC_QBUF, &buffer)) {
			printf("Error in VIDIOC_QBUF\n");
		}
	}
}

void camera_free_buffers(void)
{
	extern struct buffer *buffers;
	int i;

	for(i = 0; i < NR_OF_BUFFERS; i++) {
		v4l2_munmap(buffers[i].start, buffers[i].length);
	}
}

void camera_start(void)
{
	extern int camera_fd;	
	enum v4l2_buf_type type;
	
	type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	if (v4l2_ioctl(camera_fd, VIDIOC_STREAMON, &type)) {
		printf("Error in VIDIOC_STREAMON\n");
	}		

	sleep(1);
}

void camera_init(char *device, int width, int height)
{
	camera_open(device);
	camera_set_format(width, height);
	camera_init_buffers();
	camera_start();
}

void camera_close(void)
{
	extern int camera_fd;

	camera_free_buffers();
	v4l2_close(camera_fd);
}

PyObject *camera_to_string(void)
{
	extern unsigned char *frame;
	extern struct v4l2_format format;
	
	PyObject *result = PyString_FromStringAndSize(
      frame, format.fmt.pix.sizeimage);	
	return result;
}

void camera_capture(void)
{
	struct v4l2_buffer buffer;
	extern unsigned char *frame;
	extern struct v4l2_format format;
	
	buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
	buffer.memory = V4L2_MEMORY_MMAP;

	if (v4l2_ioctl(camera_fd, VIDIOC_DQBUF, &buffer)) {
		printf("Error in VIDIOC_DQBUF\n");
	}
	
	memcpy(frame, buffers[buffer.index].start, format.fmt.pix.sizeimage);	

	if (v4l2_ioctl(camera_fd, VIDIOC_QBUF, &buffer)) {
		printf("Error in VIDIOC_QBUF\n");
	}
}

void camera_get_px(int x, int y)
{
	extern unsigned char *frame;
	extern int bytesperpx;
	extern struct v4l2_format format;
	extern unsigned int r, g, b;

	r = frame[x * bytesperpx + y * format.fmt.pix.bytesperline];	
	g = frame[x * bytesperpx + y * format.fmt.pix.bytesperline + 1];
	b = frame[x * bytesperpx + y * format.fmt.pix.bytesperline + 2];
}

void camera_put_px(int x, int y)
{
	extern unsigned char *frame;
	extern int bytesperpx;
	extern struct v4l2_format format;
	extern unsigned int r, g, b;

	frame[x * bytesperpx + y * format.fmt.pix.bytesperline] = r;
	frame[x * bytesperpx + y * format.fmt.pix.bytesperline + 1] = g;
	frame[x * bytesperpx + y * format.fmt.pix.bytesperline + 2] = b;
}

void camera_save_frame(char *fname)
{
	extern unsigned char *frame;
	extern struct v4l2_format format;
	
	FILE *fp = fopen(fname, "w");
	fwrite(frame, format.fmt.pix.sizeimage, 1, fp);		
	fclose(fp);
}

void camera_set_control(int id, int value)
{
	struct v4l2_control control;
	extern int camera_fd;

	memset (&control, 0, sizeof (control));
	control.id = id;
	control.value = value;
	
	v4l2_ioctl(camera_fd, VIDIOC_S_CTRL, &control);
}

int camera_get_control(int id)
{
	struct v4l2_control control;
	extern int camera_fd;

	memset (&control, 0, sizeof (control));
	control.id = id;
	v4l2_ioctl(camera_fd, VIDIOC_G_CTRL, &control);

	return control.value;
}

int camera_control_available(int id)
{
	extern int camera_fd;
	struct v4l2_queryctrl queryctrl;

	memset (&queryctrl, 0, sizeof (queryctrl));
	queryctrl.id = id;
	
	if (0 == v4l2_ioctl(camera_fd, VIDIOC_QUERYCTRL, &queryctrl)) {
		if (!(queryctrl.flags & V4L2_CTRL_FLAG_DISABLED)) {
			return 1;
		}
	}
	return 0;
}

short match_at(int x, int y)
{

	/**
	Returns the match at the specified coordinates
	**/	

	extern short match[][MAX_RES_Y];	
	return match[x][y];
	
}

int color_match(int a, int b, int c, int d, int e, int f, int fuzziness)
{

	/**
	Returns 1 if the two specified colors match
	**/

	extern short match_mode;
	
	if (match_mode == MATCH_REL) {	
		int avg = (a + b + c) / 3;
		a = a - avg;
		b = b - avg;
		c = c - avg;
		
		avg = (d + e + f) / 3;
		d = d - avg;
		e = e - avg;
		f = f - avg;
	}

	if (abs(a - d) + abs(b - e) + abs(c - f) < fuzziness) {
		return 1;
	}
	return 0;
}

short matching_pixel(int *x, int *y, int *color_r, int *color_g, unsigned int *color_b, int *fuzziness)
{
	/**
	Determines whether a pixel at a specified coordinates matches the color
	**/

	extern short match_mode;
	extern int bytesperpx;
	extern struct v4l2_format format;	
	extern unsigned char *frame;
	
	long offset = (*x) * bytesperpx + (*y) * format.fmt.pix.bytesperline;
	
	int r = frame[offset];
	int g = frame[offset + 1];
	int b = frame[offset + 2];
	
	if (match_mode == MATCH_REL) {
		int avg = (r + g + b) / 3;		
		r = r - avg;
		g = g - avg;
		b = b - avg;
	}

	return abs(r - (*color_r)) + abs(g - (*color_g)) + abs(b - (*color_b)) < (*fuzziness);
}

void highlight_color(int color_r, int color_g, int color_b, int fuzziness)
{

	/**
	 * Highlights pixels matching the specified color
	 **/
	
	extern unsigned char *frame;
	extern int bytesperpx;
	extern struct v4l2_format format;
	unsigned int x, y;

	if (match_mode == MATCH_REL) {	
		int avg_col = (color_r + color_g + color_b) / 3;
		color_r = color_r - avg_col;
		color_g = color_g - avg_col;
		color_b = color_b - avg_col;
	}		
	
	for (x = 0; x < format.fmt.pix.width; x++) {
		for (y = 0; y < format.fmt.pix.height; y++) {
			if (matching_pixel(&x, &y, &color_r, &color_g, &color_b, &fuzziness)) {
				frame[x * bytesperpx + y * format.fmt.pix.bytesperline + 1] = 255;
			} else {
				frame[x * bytesperpx + y * format.fmt.pix.bytesperline] = 255;
			}
		}
	}
}

void find_object(int *color_r, int *color_g, int *color_b, int *fuzziness, int *ex, int *ey)
{

	extern struct v4l2_format format;

	int width = format.fmt.pix.width;
	int height = format.fmt.pix.height;

	int max_r = MAX(MAX((*ex), width - (*ex)), MAX((*ey), height - (*ey)));	
	
	int x, y, i;
		
	int r = 0;
	while (r < max_r) {	
	
		for (i = -r; i < r; i += SCAN_ACCURACY) {
		
			// Top-left to top-right
			x = (*ex) + i;
			y = (*ey) -r;
			
			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					(*ex) = x;
					(*ey) = y;
					return;
				}
			}
	
			// Top-right to bottom-right
			x = (*ex) + r;
			y = (*ey) + i;

			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					(*ex) = x;
					(*ey) = y;
					return;
				}
			}
					
			// Bottom-right to bottom-left
			x = (*ex) - i;
			y = (*ey) + r;
			
			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					(*ex) = x;
					(*ey) = y;
					return;
				}
			}

			// Bottom-left to top-left
			x = (*ex) - r;
			y = (*ey) - i;
			
			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					(*ex) = x;
					(*ey) = y;
					return;
				}
			}

		}
				
		r++;
	}
	
	(*ex) = -1;
	(*ey) = -1;
	return;

}

SCAN spiral_scan(int ex, int ey, int *color_r, int *color_g, int *color_b, int *fuzziness)
{

	/**
	Scans the image in a spiral fashion until the target object is found
	**/

	extern int min_z;	
	extern short match[][MAX_RES_Y];
	extern short size_mode;
	extern struct v4l2_format format;

	int width = format.fmt.pix.width;
	int height = format.fmt.pix.height;	

	short hit;
	int sx = 0;
	int sy = 0;
	int x;
	int y;
	int z = 0;
	int i;
	int r = 1;
	
	int left = ex;
	int right = ex;
	int top = ey;
	int bottom = ey;
	
	SCAN result;		
		
	if (matching_pixel(&ex, &ey, color_r, color_g, color_b, fuzziness)) { z++; }
		
	if (z == 0) {
		find_object(color_r, color_g, color_b, fuzziness, &ex, &ey);
	
		if (ex == -1) {
			result.x = -1;
			result.y = -1;
			result.count = 0;
			return result;
		}
	}

	int max_r = MAX(MAX(ex, width - ex), MAX(ey, height - ey));	
		
	while ((hit || z < min_z) && r < max_r) {
	
		hit = 0;
	
		for (i = -r; i < r; i++) {
		
			// Top-left to top-right
			x = ex + i;
			y = ey -r;
			
			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					z++;
					hit = 1;
					sx += x;
					sy += y;					
					match[x][y] = 1;
					top = y;
				} else {			
					match[x][y] = -1;
				}
			}
	
			// Top-right to bottom-right
			x = ex + r;
			y = ey + i;

			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					z++;
					hit = 1;
					sx += x;
					sy += y;					
					match[x][y] = 1;
					right = x;
				} else {			
					match[x][y] = -1;
				}
			}
					
			// Bottom-right to bottom-left
			x = ex - i;
			y = ey + r;
			
			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					z++;
					hit = 1;
					sx += x;
					sy += y;
					match[x][y] = 1;
					bottom = y;
				} else {			
					match[x][y] = -1;
				}
			}

			// Bottom-left to top-left
			x = ex - r;
			y = ey - i;
			
			if (x >= 0 && x < width && y >= 0 && y < height) {
				if (matching_pixel(&x, &y, color_r, color_g, color_b, fuzziness)) {
					z++;
					hit = 1;
					sx += x;
					sy += y;
					match[x][y] = 1;
					left = x;
				} else {			
					match[x][y] = -1;
				}
			}

		}
				
		r++;
	}
	
	if (z >= min_z) {
		result.x = sx / z;
		result.y = sy / z;
	} else {
		result.x = -1;
		result.y = -1;
		result.count = 0;
		return result;
	}
	
	if (size_mode == SIZE_SURFACE) {	
		result.count = z;	
	} else {
		result.count = (right - left) + (bottom - top);
	}
	
	return result;
}

void track_object(int color_r, int color_g, int color_b, int fuzziness, int pre_x, int pre_y, int highlight)
{

	/**
	Scans for an object
	**/

	extern short match[][MAX_RES_Y];
	extern short scan_mode;	
	extern short match_mode;
	extern int track_x;
	extern int track_y;	
	extern int track_z;	
	extern struct v4l2_format format;
	extern int bytesperpx;
	extern unsigned char *frame;		

	int width = format.fmt.pix.width;
	int height = format.fmt.pix.height;		
	
	int x, y, d, r, g, b;
	double avg_x, avg_y, avg_z;
	
	if (match_mode == MATCH_REL) {	
		int avg_col = (color_r + color_g + color_b) / 3;
		color_r = color_r - avg_col;
		color_g = color_g - avg_col;
		color_b = color_b - avg_col;
	}	
	
	avg_x = 0;
	avg_y = 0;
	avg_z = 0;
	
	int ex = MAX(0, MIN(width - pre_x, width));
	int ey = MAX(0, MIN(pre_y, height));
	
	memset(match, 0, MAX_RES_X * MAX_RES_Y * sizeof(short));	
	
	SCAN result = spiral_scan(ex, ey, &color_r, &color_g, &color_b, &fuzziness);

	if (highlight) {
		long offset;
		for (x = 0; x < width; x++) {
			for (y = 0; y < height; y++) {
				offset = x * bytesperpx + y * format.fmt.pix.bytesperline;
				if (match[x][y] == 1) {
					frame[offset + 1] = 255;
				} else if (match[x][y] == -1) {
					frame[offset] = 255;
				}
			}
		}
	}
	
	track_x = MAX(0, MIN(width - result.x, width));
	track_y = MAX(0, MIN(result.y, height));
	track_z = result.count;
	
}
