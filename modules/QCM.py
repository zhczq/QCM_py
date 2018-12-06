'''
This module is a modified version of QCM_functions.
It is used for UI, but you can also use it for data analysis.
The input and return data are all in form of DataFrame.
This module doesn't have plotting functions.

NOTE: Differnt to other modules, the harmonics used in this module are all INT.
'''


import numpy as np
from scipy.optimize import least_squares
from lmfit import Minimizer, minimize, Parameters, fit_report, printfuncs

import pandas as pd


# variable limitions
dlam_rh_range = (0, 5)
drho_range = (0, 1e-2)
grho_rh_range = (1e7, 1e13)
phi_range = (0, np.pi/2)


def nh2i(nh):
    '''
    convert harmonic (str) to index (int) 
    since only odd harmonics are stored in list
    '''
    return int((nh - 1) / 2)
    


class QCM:
    def __init__(self):
        '''
        phi in rad for calculation and exported as degree
        '''
        self.zq = 8.84e6  # shear acoustic impedance of quartz
        self.f1 = None # 5e6 Hz fundamental resonant frequency
        self.g_err_min = 10 # error floor for gamma
        self.f_err_min = 50 # error floor for f
        self.err_frac = 3e-2 # error in f or gamma as a fraction of gamma

        self.rh = None # reference harmonic for calculation
        # default values
        # self.nhcalc = '355' # harmonics used for calculating
        # self.nhplot = [1, 3, 5] # harmonics used for plotting (show calculated data)



    def fstar_err_calc(self, fstar):
        ''' 
        calculate the error in delfstar
        fstar: complex number 
        '''
        # start by specifying the error input parameters
        fstar_err = np. zeros(1, dtype=np.complex128)
        fstar_err = (self.f_err_min + self.err_frac * np.imag(fstar)) + 1j*(self.g_err_min + self.err_frac*np.imag(fstar))
        return fstar_err
        # ?? show above both imag?


    def sauerbreyf(self, n, drho):
        ''' delf_sn from Sauerbrey eq'''
        return 2 * n * self.f1**2 * drho / self.zq


    def sauerbreym(self, n, delf):
        ''' mass from Sauerbrey eq'''
        return delf * self.zq / (2 * n * self.f1**2)


    def grho(self, n, grho_rh, phi):
        ''' grho of n_th harmonic'''
        return grho_rh * (n/self.rh) ** (phi)


    def grhostar(self, n, grho_rh, phi):
        return self.grho(n, grho_rh, phi) * np.exp(1j*phi)


    def grho_from_dlam(self, n, drho, dlam, phi):
        return (drho * n * self.f1 * np.cos(phi / 2) / dlam)**2


    def grho_rh_bulk(self, delfstar):
        return (np.pi * self.zq * abs(delfstar[self.rh]) / self.f1) ** 2


    def phi_bulk(self, n, delfstar):
        return -2 * np.arctan(np.real(delfstar[n]) / np.imag(delfstar[n]))


    def lamrho_rh_calc(self, grho_rh, phi):
        return np.sqrt(grho_rh) / (self.f1 * self.f1 * np.cos(phi / 2))


    def D(self, n, drho, grho_rh, phi):
        return 2*np.pi*drho*n*self.f1*(np.cos(phi/2) - 1j * np.sin(phi/2)) / (self.grho(n, grho_rh, phi)) ** 0.5


    def DfromZ(self, n, drho, Zstar):
        return 2 * np.pi * n * self.f1 * drho / Zstar


    def zstarbulk(self, grhostar):
        return grhostar ** 0.5


    def zstarfilm(self, n, drho, grhostar):
        if grhostar == 0:
            answer = 0
        else:
            answer = self.zstarbulk(grhostar) * np.tan(2 * np.pi * n * self.f1 * drho / self.zstarbulk(grhostar)) 
        return answer


    def rstar(self, n, drho, grho_rh, phi, overlayer={'drho': 0, 'gho_rh': 0, 'phi': 0}):
        # overlayer is dictionary with drho, grho_rh and phi
        grhostar_1 = self.grhostar(n, grho_rh, phi)
        grhostar_2 = self.grhostar(n, overlayer.get('grho_rh', 0), overlayer.get('phi', 0))
        zstar_1 = self.zstarbulk(grhostar_1)
        zstar_2 = self.zstarfilm(n, overlayer.get('drho', 0), grhostar_2)   
        return zstar_2 / zstar_1
    
    
    # calcuated complex frequency shift for single layer
    def delfstarcalc(self, n, drho, grho_rh, phi, overlayer):
        rstar = self.rstar(n, drho, grho_rh, phi, overlayer)
        # overlayer is dictionary with drho, grho_rh and phi
        calc = -(self.sauerbreyf(n, drho)*np.tan(self.D(n, drho, grho_rh, phi)) / self.D(n, drho, grho_rh, phi))*(1-rstar**2) / (1+1j*rstar*np.tan(self.D(n, drho, grho_rh, phi)))
        
        # handle case where drho = 0, if it exists
        # calc[np.where(drho==0)]=0
        return calc


    # calculated complex frequency shift for bulk layer
    def delfstarcalc_bulk(self, n, grho_rh, phi):
        return ((self.f1*np.sqrt(self.grho(n, grho_rh, phi)) / (np.pi*self.zq)) * (-np.sin(phi/2)+ 1j * np.cos(phi/2)))


    def d_lamcalc(self, n, drho, grho_rh, phi):
        return drho*n*self.f1*np.cos(phi/2) / np.sqrt(self.grho(n, grho_rh, phi))


    def thin_film_gamma(self, n, drho, jdprime_rho):
        return 8*np.pi ** 2*n ** 3*self.f1 ** 4*drho ** 3*jdprime_rho / (3*self.zq)
        # same master expression, replacing grho3 with jdprime_rho3


    def grho_rh(self, jdprime_rho_rh, phi):
        return np.sin(phi)/jdprime_rho_rh


    def dlam(self, n, dlam_rh, phi):
        return dlam_rh*(n/self.rh) ** (1-phi/2)


    def normdelfstar(self, n, dlam_rh, phi):
        return -np.tan(2*np.pi*self.dlam(n, dlam_rh, phi)*(1-1j*np.tan(phi/2))) / (2*np.pi*self.dlam(n, dlam_rh, phi)*(1-1j*np.tan(phi/2)))


    def drho(self, n1, delfstar, dlam_rh, phi):
        return self.sauerbreym(n1, np.real(delfstar[n1])) / np.real(self.normdelfstar(n1, dlam_rh, phi))


    def rhcalc(self, nh, dlam_rh, phi):
        ''' nh list '''
        return self.normdelfstar(nh[0], dlam_rh, phi).real /  self.normdelfstar(nh[1], dlam_rh, phi).real


    def rhexp(self, nh, delfstar):
        return (nh[1]/nh[0])*np.real(delfstar[nh[0]]) / np.real(delfstar[nh[1]])

    def rh_from_delfstar(self, nh, delfstar):
        ''' this func is the same as rhexp!!! '''
        n1 = int(nh[0])
        n2 = int(nh[1])
        return (n2/n1)*np.real(delfstar[n1])/np.real(delfstar[n2])


    def rdcalc(self, nh, dlam_rh, phi):
        return -np.imag(self.normdelfstar(nh[2], dlam_rh, phi)) / np.real(self.normdelfstar(nh[2], dlam_rh, phi))


    def rdexp(self, nh, delfstar):
        return -np.imag(delfstar[nh[2]]) / np.real(delfstar[nh[2]])


    def rd_from_delfstar(self, n, delfstar):
        ''' dissipation ratio calculated for the relevant harmonic '''
        return -np.imag(delfstar[n])/np.real(delfstar[n])


    def bulk_guess(self, delfstar):
        ''' get the bulk solution for grho and phi '''
        grho_rh = (np.pi*self.zq*abs(delfstar[self.rh])/self.f1) ** 2
        phi = -2*np.arctan(np.real(delfstar[self.rh]) / np.imag(delfstar[self.rh]))

        # calculate rho*lambda
        lamrho_rh = np.sqrt(grho_rh)/(self.rh*self.f1*np.cos(phi/2))

        # we need an estimate for drho.  We only use this approach if it is
        # reasonably large.  We'll put it at the quarter wavelength condition
        # for now

        drho = lamrho_rh / 4
        dlam_rh = self.d_lamcalc(self.rh, drho, grho_rh, phi)

        return [dlam_rh, min(phi, np.pi/2)]


    def guess_from_props(self, drho, grho_rh, phi):
        dlam_rh = self.d_lamcalc(self.rh, drho, grho_rh, phi)
        return [dlam_rh, phi]


    def thinfilm_guess(self, delfstar):
        ''' 
        really a placeholder function until we develop a more creative strategy
        for estimating the starting point 
        '''
        return [0.05, np.pi/180*5]


########################################################



########################################################


    def solve_general(self, nh, qcm_queue, mech_queue):
        '''
        solve the property of a single test.
        nh: list of int
        qcm_queue:  QCM data. df (shape[0]=1) 
        mech_queue: initialized property data. df (shape[0]=1)
        return mech_queue
        '''
        # get fstar
        fstars = qcm_queue.fstars.iloc[0] # list
        # get delfstar
        delfstars = qcm_queue.delfstars.iloc[0] # list
        print('fstars', fstars)
        print(delfstars)
        # convert list to dict to make it easier to do the calculation
        # fstar = {int(i*2+1): fstar[i] for i, fstar in enumerate(fstars)}
        delfstar = {int(i*2+1): dfstar for i, dfstar in enumerate(delfstars)}
        print(delfstar)
        # get the marks [1st, 3rd, 5th, ...]
        marks = qcm_queue.marks.iloc[0]
        # find where the mark is not nan or None
        nhplot = [i*2+1 for i, mark in enumerate(marks) if mark != np.nan and mark is not None ]

        # fstar_err ={}
        # for n in nhplot: 
        #     fstar_err[n] = self.fstar_err_calc(fstar[n])


        # set up to handle one or two layer cases
        # overlayer set to air if it doesn't exist in soln_input
        if 'overlayer' in qcm_queue.keys():
            overlayer = qcm_queue.overlayer.iat[0, 0]
        else:
            overlayer = {'drho':0, 'grho_rh':0, 'phi':0}
        n1 = nh[0]
        n2 = nh[1]
        n3 = nh[2]

        # input variables - this is helpfulf for the error analysis
        # define sensibly names partial derivatives for further use
        deriv = {}
        err = {}
        err_names=['drho', 'grho_rh', 'phi']

        # first pass at solution comes from rh and rd
        rd_exp = self.rdexp(nh, delfstar) # nh[2]
        rh_exp = self.rhexp(nh, delfstar) # nh[0], nh[1]
        print('rd_exp', rd_exp)
        print('rh_exp', rh_exp)


        # solve the problem
        if ~np.isnan(rd_exp) or ~np.isnan(rh_exp):

            # TODO change here for the model selection
            if 'prop_guess' in qcm_queue.keys(): # value{'drho', 'grho_rh', 'phi'}
                dlam_rh, phi = self.guess_from_props(**qcm_queue.prop_guess[0])
            elif rd_exp > 0.5:
                dlam_rh, phi = self.bulk_guess(delfstar)
            else:
                dlam_rh, phi = self.thinfilm_guess(delfstar)

            print('dlam_rh', dlam_rh)
            print('phi', phi)
            params1 = Parameters()
            params1.add('dlam_rh', value=dlam_rh, min=dlam_rh_range[0], max=dlam_rh_range[1])
            params1.add('phi', value=phi, min=phi_range[0], max=phi_range[1])

            def residual1(params, rh_exp, rd_exp):
                # dlam_rh = params['dlam_rh'].value
                # phi = params['phi'].value
                return [self.rhcalc(nh, dlam_rh, phi)-rh_exp, self.rdcalc(nh, dlam_rh, phi)-rd_exp]

            mini = Minimizer(
                residual1,
                params1,
                fcn_args=(rh_exp, rd_exp),
                nan_policy='omit',
            )
            soln1 = mini.leastsq(
                # xtol=1e-7,
                # ftol=1e-7,
            )

            print(fit_report(soln1)) 
            print('success', soln1.success)
            print('message', soln1.message)
            print('lmdif_message', soln1.lmdif_message)

            dlam_rh = soln1.params.get('dlam_rh').value
            phi =soln1.params.get('phi').value
            drho = self.drho(n1, delfstar, dlam_rh, phi)
            grho_rh = self.grho_from_dlam(self.rh, drho, dlam_rh, phi)

            print(dlam_rh)
            print(phi)
            print(drho)
            print(grho_rh)

            # we solve it again to get the Jacobian with respect to our actual
            if drho_range[0]<=drho<=drho_range[1] and grho_rh_range[0]<=grho_rh<=grho_rh_range[1] and phi_range[0]<=phi<=phi_range[1]:
                params2 = Parameters()

                params2.add('drho', value=dlam_rh, min=drho_range[0], max=drho_range[1])
                params2.add('grho_rh', value=grho_rh, min=grho_rh_range[0], max=grho_rh_range[1])
                params2.add('phi', value=phi, min=phi_range[0], max=phi_range[1])

                def residual2(params, delfstar, overlayer, n1, n2, n3):
                    drho = params['drho'].value
                    grho_rh = params['grho_rh'].value
                    phi = params['phi'].value
                    return ([np.real(delfstar[n1]) -
                            np.real(self.delfstarcalc(n1, drho, grho_rh, phi, overlayer)),
                            np.real(delfstar[n2]) -
                            np.real(self.delfstarcalc(n2, drho, grho_rh, phi, overlayer)),
                            np.imag(delfstar[n3]) -
                            np.imag(self.delfstarcalc(n3, drho, grho_rh, phi, overlayer))])
                
                mini = Minimizer(
                    residual2,
                    params2,
                    fcn_args=(delfstar, overlayer, n1, n2, n3),
                    nan_policy='omit',
                )
                soln2 = mini.leastsq(
                    # xtol=1e-7,
                    # ftol=1e-7,
                )

                print(fit_report(soln2)) 
                print('success', soln2.success)
                print('message', soln2.message)
                print('lmdif_message', soln1.lmdif_message)

                # put the input uncertainties into a 3 element vector
                delfstar_err = np.zeros(3)
                delfstar_err[0] = np.real(self.fstar_err_calc(delfstar[n1]))
                delfstar_err[1] = np.real(self.fstar_err_calc(delfstar[n2]))
                delfstar_err[2] = np.imag(self.fstar_err_calc(delfstar[n3]))
                
                # initialize the uncertainties

                # recalculate solution to give the uncertainty, if solution is viable
                drho = soln2.params.get('drho').value
                grho_rh = soln2.params.get('grho_rh').value
                phi = soln2.params.get('phi').value
                dlam_rh = self.d_lamcalc(self.rh, drho, grho_rh, phi)
                jac = soln2.params.get('jac') #TODO ???
                jac_inv = np.linalg.inv(jac)

                for i, k in enumerate(err_names):
                    deriv[k]={0:jac_inv[i, 0], 1:jac_inv[i, 1], 2:jac_inv[i, 2]}
                    err[k] = ((jac_inv[i, 0]*delfstar_err[0])**2 + 
                            (jac_inv[i, 1]*delfstar_err[1])**2 +
                            (jac_inv[i, 2]*delfstar_err[2])**2)**0.5

        if np.isnan(rd_exp) or np.isnan(rh_exp) or not deriv or not err:
            # assign the default value first
            drho = np.nan
            grho_rh = np.nan
            phi = np.nan
            dlam_rh = np.nan
            for k in err_names:
                err[k] = np.nan

        # now back calculate delfstar, rh and rd from the solution
        delfstar_calc = {}
        rh = {}
        rd = {}
        delf_calcs = mech_queue.delf_calcs.iloc[0]
        delg_calcs = mech_queue.delg_calcs.iloc[0]
        rds = mech_queue.rds.iloc[0]
        print('delf_calcs', delf_calcs)
        print(type(delf_calcs))
        for n in nhplot:
            delfstar_calc[n] = self.delfstarcalc(n, drho, grho_rh, phi, overlayer)
            delf_calcs[nh2i(n)] = np.real(delfstar_calc[n])
            delg_calcs[nh2i(n)] = np.imag(delfstar_calc[n])
            
            rd[n] = self.rd_from_delfstar(n, delfstar_calc)
            rds[nh2i(n)] = rd[n]
        rh = self.rh_from_delfstar(nh, delfstar_calc)

    # drho = 1000*results[nh]['drho']
    # grho3 = results[nh]['grho3']/1000
    # phi = results[nh]['phi']
    
        # save back to mech_queue
        # single value
        mech_queue['drho'] = [drho] # in kg/m2
        mech_queue['drho_err'] = [err['drho']] # in kg/m2
        mech_queue['grho_rh'] = [grho_rh] # in Pa kg/m3
        mech_queue['grho_rh_err'] = [err['grho_rh']] # in Pa kg/m3
        mech_queue['phi'] = [phi] # in rad
        mech_queue['phi_err'] = [err['phi']] # in rad
        mech_queue['dlam_rh'] = [dlam_rh] # in na
        # mech_queue['lamrho'] = [] # in kg/m2
        # mech_queue['delrho'] = [] # in kg/m2
        # mech_queue['delf_delfsns'] = []
        mech_queue['rh'] = [rh]

        # multiple values in list
        mech_queue['delf_calcs'] = [delf_calcs]
        mech_queue['delg_calcs'] = [delg_calcs]
        # mech_queue['delg_delfsns'] = []
        mech_queue['rds'] = [rds]

        # TODO save delfstar, deriv {n1:, n2:, n3:}
                
        return mech_queue


    def all_nhcaclc_harm_not_na(self, nh, qcm_queue):
        '''
        check if all harmonics in nhcalc are not na
        nh: list of strings
        qcm_queue: qcm data (df) of a single queue
        return: True/False
        '''
        print(nh)
        print(nh2i(nh[0]))
        print(qcm_queue.delfstars.values)
        print(qcm_queue.delfstars.iloc[0])
        if np.isnan(qcm_queue.delfstars.iloc[0][nh2i(nh[0])].real) or np.isnan(qcm_queue.delfstars.iloc[0][nh2i(nh[1])].real) or np.isnan(qcm_queue.delfstars.iloc[0][nh2i(nh[2])].imag):
            return False
        else:
            return True
        
        # for h in set(nh):
        #     if np.isnan(qcm_queue.delfstar[nh2i(h)]): # both real and imag are not nan
        #         return False
        # return True


    def analyze(self, nhcalc, queue_ids, qcm_df, mech_df):
        # sample, parms
        '''
        calculate with qcm_df and save to mech_df
        '''
        nh = [int(s) for s in nhcalc] # list of harmonics (int) in nhcalc
        for queue_id in queue_ids: # iterate all ids
            print('queue_id', queue_id)
            # print('qcm_df', qcm_df)
            print(type(qcm_df))
            # queue index
            idx = qcm_df[qcm_df.queue_id == queue_id].index.astype(int)[0]
            # qcm data of queue_id
            qcm_queue = qcm_df.loc[[idx], :] # as a dataframe
            # mechanic data of queue_id
            mech_queue = mech_df.loc[[idx], :]  # as a dataframe

            # obtain the solution for the properties
            if self.all_nhcaclc_harm_not_na(nh, qcm_queue):
                # solve a single queue
                mech_queue = self.solve_general(nh, qcm_queue, mech_queue)
                # save back to mech_df
                print(mech_df.loc[[idx], :])
                print(mech_queue)
                mech_df.update(mech_queue)
            else:
                # since the df already initialized with nan values, nothing todo
                pass
        return mech_df



