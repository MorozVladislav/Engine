#!/usr/bin/env python
# coding: utf-8

from Tkinter import *
import graph as gr

class Application(Frame):

    
    RADIUS = 20
    WIDTHLINE = 3
    FONT = 14



    
    def close_win(self):
        self.master.destroy()

    
    def createWidgets(self):
        self.m = Menu(self)

        self.fm = Menu(self.m)
        self.m.add_cascade(label='File',menu = self.fm)
        #self.fm.add_command(label='Add Point', command=self.addPointCanvas)
        self.fm.add_command(label = 'Exit', command = self.close_win)

        self.master.config(menu=self.m)

        
    def movePoint(self, event):
        #coord_id = self.canv.coords(event.x, event.y,)
        x = self.canv.canvasx(event.x)
        y = self.canv.canvasy(event.y)
        obj_id = self.canv.find_overlapping(x - 5, y - 5, x + 5, y + 5)
        
    
    def createCanvas(self):
        self.canv = Canvas(self,width=700,height=700,bg="lightblue")
        self.canv.pack()
        self.canv.bind('<B1-Motion>', self.movePoint)


    #draw the point
    def addPointCanvas(self,key,x=50,y=50):
        self.canv.create_oval([x-self.RADIUS,y-self.RADIUS],[x+self.RADIUS,y+self.RADIUS],
                              fill='lightgreen',width=self.WIDTHLINE)

        self.canv.create_text(x,y,text=key,font="Verdana "+str(self.FONT))
        self.canv.pack(fill=BOTH, expand=1)

    #draw the line
    def addLineCanvas(self,x1,y1,x2,y2):
        line_id = self.canv.create_line(x1,y1,x2,y2,width=self.WIDTHLINE)
        self.canv.pack(fill=BOTH, expand=1)

    #
    def addLineCanvas2(self,x1,y1,x2,y2,key):

        medX = (x2 + x1) / 2.0
        medY = (y2 + y1) / 2.0
        length = pow(pow(x2-x1,2)+pow(y2-y1,2),0.5)

        k = 1.05 + self.FONT/length*2

        deltaX = x2 - medX
        deltaY = y2 - medY

        l1= self.canv.create_line(x1,y1,x2-deltaX*k, y2-deltaY*k,width=self.WIDTHLINE)
        l2 = self.canv.create_line(x2-deltaX/k, y2-deltaY/k, x2, y2, width=self.WIDTHLINE)
        text = self.canv.create_text(medX, medY, text=key, font="Verdana "+str(self.FONT))

        for label in self.lLabel:
            while text in self.canv.find_overlapping(label[0]-10, label[1]-10, label[0]+10, label[1]+10):
                print('see on rect1')
                self.canv.delete(text, l2)


                oldMedY = medY
                oldMedX = medX

                medY=(y2 + medY) / 2.0
                medX=(x2 + medX) / 2.0

                deltaX = x2 - medX
                deltaY = y2 - medY

                #l1 = self.canv.create_line(x2 - (x2-oldMedX) / k, y2 - (y2-oldMedY) / k, x2 - deltaX * k, y2 - deltaY * k, width=self.WIDTHLINE)
                #l2 = self.canv.create_line(x2 - deltaX / k, y2 - deltaY / k, x2, y2, width=self.WIDTHLINE)

                l1 = self.canv.create_line(x1, y1, x2 - deltaX * k,
                                           y2 - deltaY * k, width=self.WIDTHLINE)
                l2 = self.canv.create_line(x2 - deltaX / k, y2 - deltaY / k, x2, y2, width=self.WIDTHLINE)

                text = self.canv.create_text(medX, medY, text=key, font="Verdana " + str(self.FONT))



        self.lLabel.append((medX,medY))
        
    # Creatin of Adjacency List for given graph
    def buildAdjList(self):
        
        for point in self.listPoint:
            x = round((point[1]['x']+1.1)*300)
            y = round((point[1]['y']+1.1)*300)
            
            #ids = self.addPointCanvas(point[0], x, y)
            self.ovalId[point[0]] = (x,y)
            
        keys = self.ovalId.keys()
        self.pointsDict = {key: [] for key in keys}
        for point in self.listRebros:
            self.pointsDict[point[0]].append(point[1])
            self.pointsDict[point[1]].append(point[0])
        
    #So, let the draw begin!
    def initGraphRender(self):
        
        for rebro in self.listR:
            x1 = self.ovalId[rebro[0]]
            y1 = self.ovalId[rebro[0]]
            x2 = self.ovalId[rebro[1]]
            y2 = self.ovalId[rebro[1]]
            self.addLineCanvas(x1,y1,x2,y2)
        
        
        for point in self.ovalId.keys():
            self.addPointCanvas(point,self.ovalId[point][0],self.ovalId[point][1])
            
            

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.pack()

        self.lLabel = []

        self.createWidgets()
        self.createCanvas()
        
        self.ovalId = {}

        #parse the praph with our graph module
        graph = gr.Graph('big_graph.json')
        self.listPoint, self.listRebros = graph.get_coordinates()
        
        self.listR = [k[:2] for k in self.listRebros]
        
        #drawing preparations
        self.buildAdjList()
        self.initGraphRender()
        


def main():
    root = Tk()
    root.title("Граф визуальный прекрасный 1")
    app = Application(master=root)
    app.mainloop()

    
if __name__ == '__main__':
    main()

