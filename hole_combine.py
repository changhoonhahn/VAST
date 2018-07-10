from astropy.table import Table

import numpy as np

from table_functions import to_array,to_vector



################################################################################
################################################################################


def spherical_cap_volume(radius, height):
    '''Calculate the volume of a spherical cap'''

    volume = np.pi*(height**2)*(3*radius - height)/3.

    return volume


################################################################################
################################################################################


def cap_height(R, r, d):
    '''Calculate the height of a spherical cap.

    Parameters
    __________

    R : radius of sphere

    r : radius of other sphere

    d : distance between sphere centers


    Output
    ______

    h : height of cap
    '''

    h = (r - R + d)*(r + R - d)/(2*d)

    return h


################################################################################
################################################################################


def combine_holes(spheres_table, frac):
    '''
    Combines the potential void spheres into voids.

    Assumes that spheres_table is sorted by radius.
    '''

    ############################################################################
    # IDENTIFY MAXIMAL SPHERES
    #
    # We only consider holes with radii greater than 10 Mpc/h as seeds for a 
    # void.  If two holes of this size overlap by more than X% of their volume, 
    # then they are considered part of the same void.  Otherwise, they are 
    # independent voids.  The search runs from the largest hole to the smallest.
    ############################################################################

    large_spheres_boolean = spheres_table['radius'] > 10
    N_large_spheres = sum(large_spheres_boolean)
    #spheres_table = spheres_table[large_spheres_boolean]

    # Initialize index array for maximal spheres
    maximal_spheres_indices = []

    # The largest hole is a void
    N_voids = 1
    maximal_spheres_indices.append(0)

    for i in range(1,N_large_spheres):

        # Coordinates of sphere i
        sphere_i_coordinates = to_vector(spheres_table[i])
        sphere_i_coordinates = sphere_i_coordinates.T
        #print(sphere_i_coordinates.shape)
        # Radius of sphere i
        sphere_i_radius = spheres_table['radius'][i]

        ########################################################################
        #
        # COMPARE AGAINST MAXIMAL SPHERES
        #
        ########################################################################

        # Array of coordinates for previously identified maximal spheres
        maximal_spheres_coordinates = to_array(spheres_table[maximal_spheres_indices])
        # Array of radii for previously identified maximal spheres
        maximal_spheres_radii = np.array(spheres_table['radius'][maximal_spheres_indices])
        #print(maximal_spheres_coordinates.shape)
        #print(maximal_spheres_radii.shape)
        # Distance between sphere i's center and the centers of the other maximal spheres
        separation = np.linalg.norm((maximal_spheres_coordinates[0] - sphere_i_coordinates),axis=1)
        #print('max spheres',maximal_spheres_coordinates[0][:5])
        #print('sphere i',sphere_i_coordinates[:5])
        #print('subtraction',(maximal_spheres_coordinates[0] - sphere_i_coordinates)[:5])
        #print(separation.shape)
        ########################################################################
        # Does sphere i live completely inside another maximal sphere?
        ########################################################################

        if any((maximal_spheres_radii - sphere_i_radius) > separation):
            # Sphere i is completely inside another sphere --- sphere i is not a maximal sphere
            #print('sphere completely inside other sphere')
            continue

        ########################################################################
        # Does sphere i overlap by less than x% with another maximal sphere?
        ########################################################################

        # First - determine which maximal spheres sphere i does overlap with.
        overlap_boolean =  separation <= (sphere_i_radius + maximal_spheres_radii)
        '''print(sphere_i_radius)
        print(maximal_spheres_radii[:5])
        print((sphere_i_radius + maximal_spheres_radii)[:5])'''

        if any(overlap_boolean):
            #print('overlap true: maximal')
            # Sphere i overlaps at least one maximal sphere by some amount.
            # Check to see by how much.

            # Heights of the spherical caps
            height_i = cap_height(sphere_i_radius, maximal_spheres_radii[overlap_boolean], separation[overlap_boolean])

            height_maximal = cap_height(maximal_spheres_radii[overlap_boolean], sphere_i_radius, separation[overlap_boolean])

            # Overlap volume
            overlap_volume = spherical_cap_volume(sphere_i_radius, height_i) + spherical_cap_volume(maximal_spheres_radii[overlap_boolean], height_maximal)

            # Volume of sphere i
            volume_i = (4./3.)*np.pi*sphere_i_radius**3

            if all(overlap_volume <= frac*volume_i):
                # Sphere i does not overlap by more than x% with any of the other known maximal spheres.
                # Sphere i is therefore a maximal sphere.
                #print('maximal sphere')
                N_voids += 1
                maximal_spheres_indices.append(i)

        else:
            # No overlap!  Sphere i is a maximal sphere
            #print('no overlap: maximal sphere')
            N_voids += 1
            maximal_spheres_indices.append(i)


    # Extract table of maximal spheres
    maximal_spheres_table = spheres_table[maximal_spheres_indices]

    # Convert maximal_spheres_indices to numpy array of type int
    maximal_spheres_indices = np.array(maximal_spheres_indices, dtype=int)

    # Add void flag identifier to maximal spheres
    maximal_spheres_table['flag'] = np.arange(N_voids) + 1

    # Array of coordinates for maximal spheres
    maximal_spheres_coordinates = to_array(maximal_spheres_table)

    # Array of radii for maximal spheres
    maximal_spheres_radii = np.array(maximal_spheres_table['radius'])


    ############################################################################
    # ASSIGN SPHERES TO VOIDS
    #
    # A sphere is part of a void if it overlaps one maximal sphere by at least 
    # 50% of the smaller sphere's volume.
    ############################################################################


    # Initialize void flag identifier
    spheres_table['flag'] = -1

    # Number of holes
    N_spheres = len(spheres_table)

    # Initialize index array for holes
    holes_indices = []

    # Number of spheres which are assigned to a void (holes)
    N_holes = 0

    maximal_indices = np.arange(N_voids)

    for i in range(N_spheres):

        # First - check if i is a maximal sphere
        if i in maximal_spheres_indices:
            spheres_table['flag'][i] = maximal_spheres_table['flag'][maximal_spheres_indices == i]
            #print('sphere i is a maximal sphere')
            continue

        # Coordinates of sphere i
        sphere_i_coordinates = to_vector(spheres_table[i])
        sphere_i_coordinates = sphere_i_coordinates.T

        # Radius of sphere i
        sphere_i_radius = spheres_table['radius'][i]

        ########################################################################
        #
        # COMPARE AGAINST MAXIMAL SPHERES
        #
        ########################################################################

        # Distance between sphere i's center and the centers of the maximal spheres
        separation = np.linalg.norm((maximal_spheres_coordinates[0] - sphere_i_coordinates),axis=1)

        ########################################################################
        # Does sphere i live completely inside a maximal sphere?
        ########################################################################

        if any((maximal_spheres_radii - sphere_i_radius) > separation):
            # Sphere i is completely inside another sphere --- sphere i should not be saved
            print('sphere completely inside another sphere')
            continue

        ########################################################################
        # Does sphere i overlap by more than 50% with a maximal sphere?
        ########################################################################

        # First - determine which maximal spheres sphere i overlaps with
        overlap_boolean =  separation <= (sphere_i_radius + maximal_spheres_radii)
        #print('ob', overlap_boolean)
        if any(overlap_boolean):
            print('overlap true: voids')
            # Sphere i overlaps at least one maximal sphere by some amount.
            # Check to see by how much.
            maximal_overlap_indices = maximal_indices[overlap_boolean]
            # Heights of the spherical caps
            height_i = cap_height(sphere_i_radius, maximal_spheres_radii[overlap_boolean], separation[overlap_boolean])
            height_maximal = cap_height(maximal_spheres_radii[overlap_boolean], sphere_i_radius, separation[overlap_boolean])

            # Overlap volume
            overlap_volume = spherical_cap_volume(sphere_i_radius, height_i) + spherical_cap_volume(maximal_spheres_radii[overlap_boolean], height_maximal)

            # Volume of sphere i
            volume_i = (4./3.)*np.pi*sphere_i_radius**3
            # Does sphere i overlap by at least 50% of its volume with a maximal sphere?
            overlap2_boolean = overlap_volume > 0.5*volume_i
            #print(overlap_volume)
            #print('new', overlap_boolean)
            if sum(overlap2_boolean) == 1:
                # Sphere i overlaps by more than 50% with one maximal sphere
                # Sphere i is therefore a hole in that void
                print('hole inside void')
                N_holes += 1
                holes_indices.append(i)
                #print(maximal_spheres_table['flag'].shape)
                #print(overlap_boolean.shape)
                spheres_table['flag'][i] = maximal_spheres_table['flag'][maximal_overlap_indices[overlap2_boolean]]
            


    ############################################################################
    #
    #   OUTPUT TABLES
    #
    ############################################################################

    holes_table = spheres_table[holes_indices]

    return maximal_spheres_table, holes_table


################################################################################
#
#   TEST SCRIPT
#
################################################################################


if __name__ == '__main__':

    import pickle
    from astropy.table import Table

    in_file = open('potential_voids_list.txt', 'rb')
    potential_voids_table = pickle.load(in_file)
    in_file.close()

    '''fake_x = [1 2 3 4 5 6 7 8 9]
    fake_y = [1 2 3 1 2 3 1 2 3]
    fake_z = [3 2 1 1 2 3 3 2 1]
    fake_radius = [
    fake_table = Table([myvoids_x, myvoids_y, myvoids_z, myvoids_r], names=('x','y','z','radius'))'''

    maximal_spheres_table, myvoids_table = combine_holes(potential_voids_table, 0.1)

    print('Number of unique voids is', len(maximal_spheres_table))
    print('voids length',len(myvoids_table))

