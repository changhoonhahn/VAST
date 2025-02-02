"""Implementation of the ZOnes Bordering on Voids (ZOBOV) algorithm.
"""

import numpy as np
import pickle
import configparser
from scipy import stats
from astropy.table import Table

from vast.vsquared.util import toSky, inSphere, wCen, getSMA, P, flatten
from vast.vsquared.classes import Catalog, Tesselation, Zones, Voids

class Zobov:

    def __init__(self,configfile,start=0,end=3,save_intermediate=True,visualize=False,periodic=False):
        """Initialization of the ZOnes Bordering on Voids (ZOBOV) algorithm.

        Parameters
        ----------
        configfile : str
            Configuration file, in INI format.
        start : int
            Analysis stages: 0=generate catalog, 1=load catalog, 2=load tesselation, 3=load zones.
        end :  int
            Ending point: 1=generate tesselation, 2=generate zones, 3=generate voids.
        save_intermediate : bool
            If true, pickle and save intermediate outputs.
        visualize : bool
            Create visualization.
        periodic : bool
            Use periodic boundary conditions.
        """
        if start not in [0,1,2,3,4] or end not in [0,1,2,3,4] or end<start:
            print("Choose valid stages")
            return

        if visualize*periodic:
            print("Visualization not implemented for periodic boundary conditions: changing to false")
            self.visualize = False
        else:
            self.visualize = visualize
        self.periodic = periodic

        config = configparser.ConfigParser()
        config.read(configfile)

        self.infile  = config['Paths']['Input Catalog']
        self.catname = config['Paths']['Survey Name']
        self.outdir  = config['Paths']['Output Directory']
        self.intloc  = "../intermediate/" + self.catname
        
        self.H0   = float(config['Cosmology']['H_0'])
        self.Om_m = float(config['Cosmology']['Omega_m'])

        self.zmin   = float(config['Settings']['redshift_min'])
        self.zmax   = float(config['Settings']['redshift_max'])
        self.minrad = float(config['Settings']['radius_min'])
        self.zstep  = float(config['Settings']['redshift_step'])
        self.nside  = int(config['Settings']['nside'])
        self.maglim = config['Settings']['rabsmag_min']
        self.maglim = None if self.maglim=="None" else float(self.maglim)
        self.cmin = np.array([float(config['Settings']['x_min']),float(config['Settings']['y_min']),float(config['Settings']['z_min'])])
        self.cmax = np.array([float(config['Settings']['x_max']),float(config['Settings']['y_max']),float(config['Settings']['z_max'])])
        self.buff = float(config['Settings']['buffer'])


        if start<4:
            if start<3:
                if start<2:
                    if start<1:
                        ctlg = Catalog(catfile=self.infile,nside=self.nside,zmin=self.zmin,zmax=self.zmax,maglim=self.maglim,H0=self.H0,Om_m=self.Om_m,periodic=self.periodic,cmin=self.cmin,cmax=self.cmax)
                        if save_intermediate:
                            pickle.dump(ctlg,open(self.intloc+"_ctlg.pkl",'wb'))
                    else:
                        ctlg = pickle.load(open(self.intloc+"_ctlg.pkl",'rb'))
                    if end>0:
                        tess = Tesselation(ctlg,viz=self.visualize,periodic=self.periodic,buff=self.buff)
                        if save_intermediate:
                            pickle.dump(tess,open(self.intloc+"_tess.pkl",'wb'))
                else:
                    ctlg = pickle.load(open(self.intloc+"_ctlg.pkl",'rb'))
                    tess = pickle.load(open(self.intloc+"_tess.pkl",'rb'))
                if end>1:
                    zones = Zones(tess,viz=visualize)
                    if save_intermediate:
                        pickle.dump(zones,open(self.intloc+"_zones.pkl",'wb'))
            else:
                ctlg  = pickle.load(open(self.intloc+"_ctlg.pkl",'rb'))
                tess  = pickle.load(open(self.intloc+"_tess.pkl",'rb'))
                zones = pickle.load(open(self.intloc+"_zones.pkl",'rb'))
            if end>2:
                voids = Voids(zones)
                if save_intermediate:
                    pickle.dump(voids,open(self.intloc+"_voids.pkl",'wb'))
        else:
            ctlg  = pickle.load(open(self.intloc+"_ctlg.pkl",'rb'))
            tess  = pickle.load(open(self.intloc+"_tess.pkl",'rb'))
            zones = pickle.load(open(self.intloc+"_zones.pkl",'rb'))
            voids = pickle.load(open(self.intloc+"_voids.pkl",'rb'))
        self.catalog = ctlg
        if end>0:
            self.tesselation = tess
        if end>1:
            self.zones       = zones
        if end>2:
            self.prevoids    = voids


    def sortVoids(self, method=0, minsig=2, dc=0.2):
        """
        Sort voids according to one of several methods.

        Parameters
        ==========

        method : int
            0 = VIDE method (arXiv:1406.1191); link zones with density <1/5 mean density, and remove voids with density >1/5 mean density.
            1 = ZOBOV method (arXiv:0712.3049); keep full void hierarchy.
            2 = ZOBOV method; cut voids over a significance threshold.
            3 = not available
            4 = REVOLVER method (arXiv:1904.01030); every zone below mean density is a void.
        
        minsig : float
            Minimum significance threshold for selecting voids.

        dc : float
            Density cut for linking zones using VIDE method.
        """

        if not hasattr(self,'prevoids'):
            if method != 4:
                print("Run all stages of Zobov first")
                return
            else:
                if not hasattr(self,'zones'):
                    print("Run all stages of Zobov first")
                    return

        # Selecting void candidates
        print("Selecting void candidates...")

        if method==0:
            #print('Method 0')
            voids  = []
            minvol = np.mean(self.tesselation.volumes[self.tesselation.volumes>0])/dc
            for i in range(len(self.prevoids.ovols)):
                vl = self.prevoids.ovols[i]
                vbuff = []

                for j in range(len(vl)-1):
                    if j > 0 and vl[j] < minvol:
                        break
                    vbuff.extend(self.prevoids.voids[i][j])
                voids.append(vbuff)

        elif method==1:
            #print('Method 1')
            voids = [[c for q in v for c in q] for v in self.prevoids.voids]

        elif method==2:
            #print('Method 2')
            voids = []
            for i in range(len(self.prevoids.mvols)):
                vh = self.prevoids.mvols[i]
                vl = self.prevoids.ovols[i][-1]

                r  = vh / vl
                p  = P(r)

                if stats.norm.isf(p/2.) >= minsig:
                    voids.append([c for q in self.prevoids.voids[i] for c in q])

        elif method==3:
            print("Method 3 coming soon")
            return

        elif method==4:
            #print('Method 4')
            voids = np.arange(len(self.zones.zvols)).reshape(len(self.zones.zvols),1).tolist()

        else:
            print("Choose a valid method")
            return

        print('Void candidates selected...')

        vcuts = [list(flatten(self.zones.zcell[v])) for v in voids]

        gcut  = np.arange(len(self.catalog.coord))[self.catalog.nnls==np.arange(len(self.catalog.nnls))]
        cutco = self.catalog.coord[gcut]

        # Build array of void volumes
        vvols = np.array([np.sum(self.tesselation.volumes[vcut]) for vcut in vcuts])

        # Calculate effective radius of voids
        vrads = (vvols*3/(4*np.pi))**(1/3)
        print('Effective void radius calculated')

        # Locate all voids with radii smaller than set minimum
        if method==4:
            self.minrad = np.median(vrads)
        rcut  = vrads > self.minrad
        
        voids = np.array(voids)[rcut]

        vcuts = [vcuts[i] for i in np.arange(len(rcut))[rcut]]
        vvols = vvols[rcut]
        vrads = vrads[rcut]
        print('Removed voids smaller than', self.minrad, 'Mpc/h')

        # Identify void centers.
        print("Finding void centers...")
        vcens = np.array([wCen(self.tesselation.volumes[vcut],cutco[vcut]) for vcut in vcuts])
        if method==0:
            dcut  = np.array([64.*len(cutco[inSphere(vcens[i],vrads[i]/4.,cutco)])/vvols[i] for i in range(len(vrads))])<1./minvol
            vrads = vrads[dcut]
            rcut  = vrads>(minvol*dc)**(1./3)
            vrads = vrads[rcut]
            vcens = vcens[dcut][rcut]
            voids = (voids[dcut])[rcut]

        # Identify eigenvectors of best-fit ellipsoid for each void.
        print("Calculating ellipsoid axes...")

        vaxes = np.array([getSMA(vrads[i],cutco[vcuts[i]]) for i in range(len(vrads))])

        zvoid = [[-1,-1] for _ in range(len(self.zones.zvols))]

        for i in range(len(voids)):
            for j in voids[i]:
                if zvoid[j][0] > -0.5:
                    if len(voids[i]) < len(voids[zvoid[j][0]]):
                        zvoid[j][0] = i
                    elif len(voids[i]) > len(voids[zvoid[j][1]]):
                        zvoid[j][1] = i
                else:
                    zvoid[j][0] = i
                    zvoid[j][1] = i

        self.vrads = vrads
        self.vcens = vcens
        self.vaxes = vaxes
        self.zvoid = np.array(zvoid)


    def saveVoids(self):
        """Output calculated voids to an ASCII file [catalogname]_zonevoids.dat.
        """
        if not hasattr(self,'vcens'):
            print("Sort voids first")
            return
        vcen = self.vcens.T
        vax1 = np.array([vx[0] for vx in self.vaxes]).T
        vax2 = np.array([vx[1] for vx in self.vaxes]).T
        vax3 = np.array([vx[2] for vx in self.vaxes]).T

        if self.periodic:
            vT = Table([vcen[0],vcen[1],vcen[2],self.vrads,vax1[0],vax1[1],vax1[2],vax2[0],vax2[1],vax2[2],vax3[0],vax3[1],vax3[2]],
                    names=('x','y','z','radius','x1','y1','z1','x2','y2','z2','x3','y3','z3'))
        else:
            vz,vra,vdec = toSky(self.vcens,self.H0,self.Om_m,self.zstep)
            vT = Table([vcen[0],vcen[1],vcen[2],vz,vra,vdec,self.vrads,vax1[0],vax1[1],vax1[2],vax2[0],vax2[1],vax2[2],vax3[0],vax3[1],vax3[2]],
                    names=('x','y','z','redshift','ra','dec','radius','x1','y1','z1','x2','y2','z2','x3','y3','z3'))

        vT.write(self.outdir+self.catname+"_zobovoids.dat",format='ascii.commented_header',overwrite=True)

        vZ = Table([np.array(range(len(self.zvoid))),(self.zvoid).T[0],(self.zvoid).T[1]],
                    names=('zone','void0','void1'))
        vZ.write(self.outdir+self.catname+"_zonevoids.dat", 
                 format='ascii.commented_header', 
                 overwrite=True)


    def saveZones(self):
        """Output calculated zones to an ASCII file [catalogname]_galzones.dat.
        """

        if not hasattr(self,'zones'):
            print("Build zones first")
            return

        ngal  = len(self.catalog.coord)
        glist = np.arange(ngal)
        glut1 = glist[self.catalog.nnls==glist]
        glut2 = [[] for _ in glut1]
        dlist = -1 * np.ones(ngal,dtype=int)

        for i,l in enumerate(glut2):
            l.extend((glist[self.catalog.nnls==glut1[i]]).tolist())
            dlist[l] = self.zones.depth[i]

        zlist = -1 * np.ones(ngal,dtype=int)
        zcell = self.zones.zcell

        olist = 1-np.array(self.catalog.imsk,dtype=int)
        elist = np.zeros(ngal,dtype=int)

        for i,cl in enumerate(zcell):
            for c in cl:
                zlist[glut2[c]] = i
                if self.tesselation.volumes[c]==0. and not olist[glut2[c]].all():
                    elist[glut2[c]] = 1
        elist[np.array(olist,dtype=bool)] = 0

        zT = Table([glist,zlist,dlist,elist,olist],names=('gal','zone','depth','edge','out'))
        zT.write(self.outdir+self.catname+"_galzones.dat",format='ascii.commented_header',overwrite=True)


    def preViz(self):
        """Pre-computations needed for zone and void visualizations. Produces
        an ASCII file [catalogname]_galviz.dat.
        """

        if not self.visualize:
            print("Rerun with visualize=True")
            return
        if not hasattr(self,'vcens'):
            print("Sort voids first")
            return

        galc = self.catalog.coord[self.catalog.nnls==np.arange(len(self.catalog.coord))]
        gids = np.arange(len(self.catalog.coord))
        gids = gids[self.catalog.nnls==gids]
        g2v = -1*np.ones(len(self.catalog.coord),dtype=int)
        g2v2 = -1*np.ones(len(self.catalog.coord),dtype=int)
        verc = self.tesselation.verts
        zverts = self.zones.zverts
        znorms = self.zones.znorms
        z2v = self.zvoid.T[1]
        z2v2 = np.array([np.where(z2v==z2)[0] for z2 in np.unique(z2v[z2v!=-1])])
        zcut = [np.product([np.product(self.tesselation.volumes[self.zones.zcell[z]])>0 for z in z2])>0 for z2 in z2v2]

        tri1 = []
        tri2 = []
        tri3 = []
        norm = []
        vid  = []

        for k,v in enumerate(z2v2[zcut]):
            for z in v:
                for i in range(len(znorms[z])):
                    p = znorms[z][i]
                    n = galc[p[1]] - galc[p[0]]
                    n = n/np.sqrt(np.sum(n**2.))
                    polids = zverts[z][i]
                    trids = [[polids[0],polids[j],polids[j+1]] for j in range(1,len(polids)-1)]
                    for t in trids:
                        tri1.append(verc[t[0]])
                        tri2.append(verc[t[1]])
                        tri3.append(verc[t[2]])
                        norm.append(n)
                        vid.append(k)
                    g2v[gids[p[0]]] = k
        for k,v in enumerate(z2v2[zcut]):
            for z in v:
                for i in range(len(znorms[z])):
                    if g2v[gids[p[1]]] != -1:
                        g2v2[gids[p[1]]] = k

        if len(vid)==0:
            print("Error: largest void found encompasses entire survey (try using a method other than 1 or 2)")
            return

        tri1 = np.array(tri1).T
        tri2 = np.array(tri2).T
        tri3 = np.array(tri3).T
        norm = np.array(norm).T
        vid = np.array(vid)

        vizT = Table([vid,norm[0],norm[1],norm[2],tri1[0],tri1[1],tri1[2],tri2[0],tri2[1],tri2[2],tri3[0],tri3[1],tri3[2]],
                     names=('void_id','n_x','n_y','n_z','p1_x','p1_y','p1_z','p2_x','p2_y','p2_z','p3_x','p3_y','p3_z'))
        vizT.write(self.outdir+self.catname+"_triangles.dat",format='ascii.commented_header',overwrite=True)
        g2vT = Table([np.arange(len(g2v)),g2v,g2v2],names=('gid','g2v','g2v2'))
        g2vT.write(self.outdir+self.catname+"_galviz.dat",format='ascii.commented_header',overwrite=True)
