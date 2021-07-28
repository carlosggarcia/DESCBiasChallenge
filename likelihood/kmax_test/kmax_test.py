from cobaya.model import get_model
from cobaya.run import run
from shutil import copyfile
import yaml
import os
import sys
import numpy as np
import numpy.linalg as LA 

kmax = sys.argv[1]
print('kmax = ',kmax)

copyfile("kmax_test.yml", "kmax_"+kmax+".yml")

new_yml = open("kmax_"+kmax+".yml", "a")
new_yml.write("      kmax: "+kmax+"\ndebug: True\noutput: 'cobaya_out/kmax_test'")
new_yml.close()

# Read in the yaml file
config_fn = "kmax_"+kmax+".yml"
with open(config_fn, "r") as fin:
    info = yaml.load(fin, Loader=yaml.FullLoader)

# Get the mean proposed in the yaml file for each parameter
p0 = {}
for p in info['params']:
     if isinstance(info['params'][p], dict):
         if 'ref' in info['params'][p]:
             p0[p] = info['params'][p]['ref']['loc']
os.system('mkdir -p ' + info['output'])

print("params_dict = ", p0)

# Compute the likelihood
model = get_model(info)
loglikes, derived = model.loglikes(p0)
print("chi2 = ", -2 * loglikes[0])

# Run minimizer
updated_info, sampler = run(info)
bf = sampler.products()['minimum'].bestfit()
pf = {k: bf[k] for k in p0.keys()}
print("Final params: ")
print(pf)

#======================DETERMINE ERRORS ON PARAMETERS========================

# remove cobaya_out directory (just for now!) to make running code easier
os.system('rm -r cobaya_out')  

class Fisher:
    def __init__(self,pf):
        self.pf = pf
    
    # Determine likelihood at new steps
    def fstep(self,param1,param2,h1,h2,signs):   
        newp = self.pf.copy()
        newp[param1] = self.pf[param1] + signs[0]*h1
        newp[param2] = self.pf[param2] + signs[1]*h2
    
        newloglike = model.loglikes(newp)
    
        return -1*newloglike[0]

    # Fisher matrix elements
    def F_ij(self,param1,param2,h1,h2):  
        # Diagonal elements
        if param1==param2:  
            f1 = self.fstep(param1,param2,h1,h2,(0,+1))
            f2 = self.fstep(param1,param2,h1,h2,(0,0))
            f3 = self.fstep(param1,param2,h1,h2,(0,-1))
            F_ij = (f1-2*f2+f3)/(h2**2)
        # Off-diagonal elements     
        else:  
            f1 = self.fstep(param1,param2,h1,h2,(+1,+1))
            f2 = self.fstep(param1,param2,h1,h2,(-1,+1))
            f3 = self.fstep(param1,param2,h1,h2,(+1,-1))
            f4 = self.fstep(param1,param2,h1,h2,(-1,-1))
            F_ij = (f1-f2-f3+f4)/(4*h1*h2)
            
        return F_ij[0]

    # Calculate Fisher matrix
    def calc_Fisher(self):
        h_fact = 0.005 # stepsize factor

        # typical variations of each parameter
        typ_var = {"sigma8": 0.1,"Omega_c": 0.5,"Omega_b": 0.2,"h": 0.5,"n_s": 0.2,"m_nu": 0.1,
                   "cllike_cl1_b0": 0.1,"cllike_cl2_b0": 0.1,"cllike_cl3_b0": 0.1,"cllike_cl4_b0": 0.1,"cllike_cl5_b0": 0.1,"cllike_cl6_b0": 0.1}  

        theta = list(self.pf.keys())  # array containing parameter names

        # Assign matrix elements
        F = np.zeros([len(theta),len(theta)])
        for i in range(0,len(theta)):
            for j in range(0,len(theta)):
                param1 = theta[i]
                param2 = theta[j]
                h1 = h_fact*typ_var[param1]
                h2 = h_fact*typ_var[param2]
                F[i][j] = self.F_ij(param1,param2,h1,h2)
                
        return F
    
    # Determine condition number of Fisher matrix
    def get_cond_num(self):
        cond_num = LA.cond(self.calc_Fisher())
        return cond_num
        
    # Get errors on parameters
    def get_err(self):
        covar = LA.inv(self.calc_Fisher())  # covariance matrix
        err = np.sqrt(np.diag(covar))  # estimated parameter errors
        return err

p0vals = list(p0.values())
pfvals = list(pf.values())
final_params = Fisher(pf)
errs = list(final_params.get_err())

data = np.column_stack([float(kmax)] + p0vals + pfvals + errs)
head = 'PARAMETERS: \nkmax   true_params('+str(len(p0vals))+')   calc_params('+str(len(pfvals))+')   errors('+str(len(errs))+')'
out = open('kmax_test.dat','a')
np.savetxt(out, data, header=head)
out.close()

os.system('rm kmax_'+kmax+'.yml')