#!/usr/bin/env python2
import cv, sys, numpy, argparse

def seqToList(cvseq):
  list = []
  while cvseq is not None:
    list.append(cvseq)
    cvseq = cvseq.h_next()
  return list

def tInt(t):
  return tuple([int(x) for x in t])

class Splitter:
  def parseArgs(self):
    parser = argparse.ArgumentParser(description = 'Photo splitter')
    parser.add_argument('-i', '--interactive', action='store_true')
    parser.add_argument('-s', '--saveName')
    parser.add_argument('filename')
    self.args = parser.parse_args()
    if self.args.saveName is None:
      self.args.saveName = self.args.filename[0:-4]

  def __init__(self):
    self.parseArgs()
    self.img = cv.LoadImage(self.args.filename)
    if self.args.interactive and self.img.width > 800:
      scale = 800.0 / self.img.width 
      #print(scale, self.img.width, self.img.height, self.img.width * scale, self.img.height * scale)
      small = cv.CreateImage((int(scale * self.img.width), int(scale * self.img.height)), cv.IPL_DEPTH_8U, 3)
      cv.Resize(self.img, small)
      self.img = small
      cv.ShowImage("orig", self.img)
    self.grey = cv.CreateImage(cv.GetSize(self.img), 8, 1)
    cv.CvtColor(self.img, self.grey, cv.CV_BGR2GRAY)
    self.font = cv.InitFont(cv.CV_FONT_HERSHEY_PLAIN, 1.0, 1.0)
    self.changeContourMethod()
    self.registerKeys()

  def process(self):
    if self.args.interactive:
      self.loop()
    else:
      self.findContours(240)

  def processPhoto(self, photo):
    if self.args.interactive:
      cv.ShowImage('Output', photo)
      cv.WaitKey(0)
    else:
      self.savePhoto(photo)

  def savePhoto(self, photo):
    if not hasattr(self, '_photoIdx'): self._photoIdx = 0 
    self._photoIdx += 1
    filename = "%s_%s.jpg" % (self.args.saveName, self._photoIdx)
    print("Saving: ", filename)
    cv.SaveImage(filename, photo)

  def registerKeys(self):
    self.keys = {}
    self.keys[27] = self.keys[10] = lambda : sys.exit(0) # ESC or ENTER
    self.keys[190] = lambda : self.changeContourMethod() # F1

  def loop(self):
    while True:
      key = cv.WaitKey(10)
      if key == -1: continue
      key = key % 256
      if key in self.keys:
        self.keys[key]()
      else:
        print key, chr(key)
        sys.stdout.flush()
        

  def test(self, method, min=0, to=100, init=0, step=1):
    name = method.__name__
    setattr(self, '_test_' + name, True)
    cv.NamedWindow(name, cv.CV_WINDOW_AUTOSIZE)
    range = (to - min) / step
    cv.CreateTrackbar(name, name, init, range, lambda v: self.testValue(method, v * step + min))
    self.testValue(method, init)

  def testValue(self, method, value):
    img = method(value)
    cv.PutText(img, str(value), (10, 20), self.font, 255)
    cv.ShowImage(method.__name__, img)

  def changeContourMethod(self):
    if not hasattr(self, 'contourMethod'):
      self.contourMethod = 0
      self.contourMethods = [
        (cv.CV_RETR_EXTERNAL, cv.CV_CHAIN_CODE, 'chain_code'),
        (cv.CV_RETR_EXTERNAL, cv.CV_CHAIN_APPROX_NONE, 'approx_none'),
        (cv.CV_RETR_EXTERNAL, cv.CV_CHAIN_APPROX_SIMPLE, 'approx_simple'),
        (cv.CV_RETR_EXTERNAL, cv.CV_CHAIN_APPROX_TC89_L1, 'tc89_l1'),
        (cv.CV_RETR_EXTERNAL, cv.CV_CHAIN_APPROX_TC89_KCOS, 'tc89_kcos'),
        (cv.CV_RETR_LIST, cv.CV_LINK_RUNS, 'link_runs')
      ]
    self.contourMethod = (self.contourMethod + 1) % len(self.contourMethods)
    if hasattr(self, '_test_findContours'): self.testValue(self.findContours, self._lastTrackValue)

  def plausiblePhoto(self, contour):
    if len(contour) < 4: return False
    center, size, angle = cv.MinAreaRect2(contour)
    if size[0] < size[1]: size = (size[1], size[0])
    if size[1] < 0.001 : return False
    ratio = size[0] / size[1]
    if ratio > 2.5: return False
    return True

  def findContours(self, value):
    self._lastTrackValue = value
    out = self.adaptiveThreshold(value)
    method = self.contourMethods[self.contourMethod]
    storage = cv.CreateMemStorage()
    contour = cv.FindContours(out, storage, method[0], method[1])
    out = cv.CloneImage(self.img)
    if contour:
      contours = [( cv.ContourArea(x), x ) for x in seqToList(contour) if self.plausiblePhoto(x)]
      area_max = max([a for (a, s) in contours])
      contours = [c for (a, c) in contours if area_max / max([a, 0.001]) < 10]
      for contour in contours:
        self.processPhoto(self.processContour(contour, out))
    cv.PutText(out, method[2], (50, 20), self.font, (255, 0, 0))
    return out

  def processContour(self, contour, img):
    storage = cv.CreateMemStorage()
    box = (center, size, angle) = cv.MinAreaRect2(contour)
    box_points = cv.BoxPoints(box)
    points = [(int(x[0]), int(x[1])) for x in box_points]

    transl_mat = cv.CreateMat(2, 3, cv.CV_32F)

    img_center = (img.width / 2, img.height / 2)
    half_size = [d / 2 for d in size]
    p_from = box_points[0:3]
    p_to = [
      (img_center[0] + half_size[0], img_center[1] - half_size[1]),
      (img_center[0] + half_size[0], img_center[1] + half_size[1]),
      (img_center[0] - half_size[0], img_center[1] + half_size[1]),
      (img_center[0] - half_size[0], img_center[1] - half_size[1])
    ]
    cv.GetAffineTransform(p_from, p_to, transl_mat)

    out = cv.CloneImage(img)
    cv.WarpAffine(img, out, transl_mat)
    #cv.PolyLine(img, [map(tInt, p_from), map(tInt, p_to)], False, (0, 0, 255), 3)
    #cv.PolyLine(out, [map(tInt, p_to)], True, (0, 255, 0), 3)
    rect = (p_to[3][0], p_to[3][1], size[0], size[1])
    cv.SetImageROI(out, tuple(map(int, rect)))
    return out

  # not working at all
  def segmentation(self, value):
    storage = cv.CreateMemStorage(1000)
    level = 3
    mask = -(1 << level)
    grey = self.grey
    cv.SetImageROI(grey, (0, 0, grey.width & mask, grey.height & mask))
    out = cv.CloneImage(grey)
    grey = self.adaptiveThreshold(31)
    contour = cv.PyrSegmentation(grey, out, storage, level, value, 30)
    if contour:
      for c in contour:
        area, color, rect = c
        cv.Rectangle(out, rect[0:2], rect[2:4], 100, 3, cv.CV_AA)
    return out

  def threshold(self, value):
    binary = cv.CloneImage(self.grey)
    cv.Threshold(binary, binary, value, 255, cv.CV_THRESH_BINARY_INV)
    return binary

  def adaptiveThreshold(self, value):
    if value < 3: value = 3
    if value % 2 == 0: value += 1
    binary = cv.CloneImage(self.grey)
    cv.AdaptiveThreshold(binary, binary, 255, cv.CV_ADAPTIVE_THRESH_MEAN_C, cv.CV_THRESH_BINARY_INV, value)
    #cv.AdaptiveThreshold(grey, binary, 255, cv.CV_ADAPTIVE_THRESH_GAUSSIAN_C, cv.CV_THRESH_BINARY_INV, value)
    return binary

  def canny(self, t1 = 10, t2 = 100):
    can = cv.CloneImage(self.grey)
    cv.Canny(can, can, t1, t2, 3);
    return can

splitter = Splitter()
splitter.process()
#splitter.test(splitter.adaptiveThreshold, 3, 100, 3, 2)
#splitter.test(splitter.threshold, 1, 255, 240)
#splitter.test(splitter.canny, 1, 255, 240)
#splitter.test(splitter.segmentation, 1, 255, 240)
#splitter.test(splitter.findContours, 3, 255, 240)
