"""
This file is part of Mantra.

Mantra is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Mantra is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Mantra.  If not, see <http://www.gnu.org/licenses/>.
"""

class calibrate:

	"""
	This class translates coordinates as recorded by the webcam to real-world coordinates.
	Calibration is achieved by performing a multiple linear regression analysis for each real-world coordinate,
	using the three webcam-coordinates as independent variables.
	"""

	def __init__(self):	
	
		"""
		Initializes the calibration module
		"""
	
		self.pts = []
		self.calibrated = False

	def calibrate(self):
	
		"""
		Performs a calibration based on the available datapoints.				
		"""
		
		from rpy import r
	
		if len(self.pts) < 2:
			return False

		in_x = []
		in_y = []
		in_z = []
		out_x = []
		out_y = []
		out_z = []

		# Index all points so they can be fed into the R multiple linear regression
		for in_pt, out_pt in self.pts:
			in_x.append(in_pt[0])
			in_y.append(in_pt[1])
			in_z.append(in_pt[2])
			out_x.append(out_pt[0])
			out_y.append(out_pt[1])
			out_z.append(out_pt[2])
		
		# Perform the regression analysis
		fx = r.lm(r("x ~ a + b + c"), data = r.data_frame(a=in_x, b=in_y, c=in_z, x=out_x))["coefficients"]
		fy = r.lm(r("y ~ a + b + c"), data = r.data_frame(a=in_x, b=in_y, c=in_z, y=out_y))["coefficients"]
		fz = r.lm(r("z ~ a + b + c"), data = r.data_frame(a=in_x, b=in_y, c=in_z, z=out_z))["coefficients"]		
	
		self.fx = fx["(Intercept)"], fx["a"], fx["b"], fx["c"]
		self.fy = fy["(Intercept)"], fy["a"], fy["b"], fy["c"]
		self.fz = fz["(Intercept)"], fz["a"], fz["b"], fz["c"]
								
		self.calibrated = True
		
		return True		

	def estimate(self, pt):
	
		"""
		Translates measured coordinates to actual coordinates.
		"""
		
		if not self.calibrated:
			return pt
		
		return (self.fx[0] + self.fx[1] * pt[0] + self.fx[2] * pt[1] + self.fx[3] * pt[2]
			, self.fx[0] + self.fy[1] * pt[0] + self.fy[2] * pt[1] + self.fy[3] * pt[2]
			, self.fx[0] + self.fy[1] * pt[0] + self.fz[2] * pt[1] + self.fz[3] * pt[2])

