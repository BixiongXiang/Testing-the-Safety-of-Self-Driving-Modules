'''
usage: python gen_diff.py -h
'''

from __future__ import print_function

import argparse

from scipy.misc import imsave

from driving_models import *
from utils import *

# read the parameter
# argument parsing
parser = argparse.ArgumentParser(
    description='Main function for difference-inducing input generation in Driving dataset')
parser.add_argument('transformation', help="realistic transformation type",
                    choices=['light', 'occl', 'blackout', 'color']) # add parameter
parser.add_argument('weight_diff', help="weight hyperparm to control differential behavior", type=float)
parser.add_argument('weight_nc', help="weight hyperparm to control neuron coverage", type=float)
parser.add_argument('step', help="step size of gradient descent", type=float)
parser.add_argument('seeds', help="number of seeds of input", type=int)
parser.add_argument('grad_iterations', help="number of iterations of gradient descent", type=int)
parser.add_argument('threshold', help="threshold for determining neuron activated", type=float)
parser.add_argument('-t', '--target_model', help="target model that we want it predicts differently",
                    choices=[0, 1, 2], default=0, type=int)
parser.add_argument('-sp', '--start_point', help="occlusion upper left corner coordinate", default=(0, 0), type=tuple)
parser.add_argument('-occl_size', '--occlusion_size', help="occlusion size", default=(50, 50), type=tuple)

args = parser.parse_args()

# input image dimensions
img_rows, img_cols = 100, 100
input_shape = (img_rows, img_cols, 3)

# define input tensor as a placeholder
input_tensor = Input(shape=input_shape)

# load multiple models sharing same input tensor
K.set_learning_phase(0)
model1 = Dave_orig(input_tensor=input_tensor, load_weights=True)
model2 = Dave_norminit(input_tensor=input_tensor, load_weights=True)
model3 = Dave_dropout(input_tensor=input_tensor, load_weights=True)
# init coverage table
model_layer_dict1, model_layer_dict2, model_layer_dict3 = init_coverage_tables(model1, model2, model3)

# my func

def colorChange(img):
    width = img.shape[0]
    height = img.shape[1]
    for i in range(0, width):
        for j in range(0, height):
            img[i][j][0] = 0.9 * img[i][j][0]
            img[i][j][1] = 0.6 * img[i][j][1]
            img[i][j][2] = 0.2 * img[i][j][2]

    return img

def myFisheye(img, size):
    rows = img.shape[0]
    cols = img.shape[1]

    tx = (int)((rows / 2) + random.randint(1, 10))
    ty = (int)((cols / 2) + random.randint(1, 10))

    r = size # recommand 20 for 100 x 100 picture

    for row in range(tx - r, tx + r):
        for col in range(ty - r, ty + r):
            dist = math.sqrt(math.pow(row - tx, 2) + math.pow(col - ty, 2))

            if (dist < r and col < cols and row < rows):
                # img->at < Vec3b > (row, col) = img->at < Vec3b > (row + dist * (tx - row) / 150, col + dist * (tx - row) / 150);
                dx = (int)(row + dist * (tx - row) / 150)
                dy = (int)(col + dist * (tx - row) / 150)

                img[row][col][0] = img[dx][dy][0]
                img[row][col][1] = img[dx][dy][1]
                img[row][col][2] = img[dx][dy][2]



    return img

# reconmmand strength is 2
def myBlur(img, strength):
    rows = img.shape[0]
    cols = img.shape[1]

    cv2.blur(img, (strength, strength), img)
    return img
# ==============================================================================================
# start gen inputs

img_paths = image.list_pictures('./testing/center', ext='jpg')
for _ in range(args.seeds):
    path = random.choice(img_paths)
    gen_img = preprocess_image(path)
    orig_img = gen_img.copy()

    my_image = cv2.imread(path)
    my_image = cv2.cvtColor(my_image, cv2.COLOR_BGR2RGB)
    y = my_image.shape[0]
    x = my_image.shape[1]

    # for i in range(0, x):
    #     for j in range(0, y):
    #         tmp = my_image[j, i, 0]
    #         my_image[j, i, 0] = my_image[j, i, 2]
    #         my_image[j, i, 2] = my_image[j, i, 1]
    #         my_image[j, i, 2] = tmp

    Copy = np.zeros(my_image.shape, np.uint8)
    Copy = my_image.copy()


    imsave('./generated_inputs/' + 'Copy' + '.jpg', my_image)

    # print(gen_img[0][1][1])
    # gen_img[0][1][1] = [0, 0, 0]
    # print(gen_img[0][1][1])
    # gen_img[0][1][1][0] = 12
    # print(gen_img[0][1][1][0])

    # first check if input already induces differences
    angle1, angle2, angle3 = model1.predict(gen_img)[0], model2.predict(gen_img)[0], model3.predict(gen_img)[0]
    if angle_diverged(angle1, angle2, angle3):
        print(bcolors.OKGREEN + 'input already causes different outputs: {}, {}, {}'.format(angle1, angle2,
                                                                                            angle3) + bcolors.ENDC)

        update_coverage(gen_img, model1, model_layer_dict1, args.threshold)
        update_coverage(gen_img, model2, model_layer_dict2, args.threshold)
        update_coverage(gen_img, model3, model_layer_dict3, args.threshold)

        print(bcolors.OKGREEN + 'covered neurons percentage %d neurons %.3f, %d neurons %.3f, %d neurons %.3f'
              % (len(model_layer_dict1), neuron_covered(model_layer_dict1)[2], len(model_layer_dict2),
                 neuron_covered(model_layer_dict2)[2], len(model_layer_dict3),
                 neuron_covered(model_layer_dict3)[2]) + bcolors.ENDC)
        averaged_nc = (neuron_covered(model_layer_dict1)[0] + neuron_covered(model_layer_dict2)[0] +
                       neuron_covered(model_layer_dict3)[0]) / float(
            neuron_covered(model_layer_dict1)[1] + neuron_covered(model_layer_dict2)[1] +
            neuron_covered(model_layer_dict3)[
                1])
        print(bcolors.OKGREEN + 'averaged covered neurons %.3f' % averaged_nc + bcolors.ENDC)

        gen_img_deprocessed = draw_arrow(deprocess_image(gen_img), angle1, angle2, angle3)

        # save the result to disk
        imsave('./generated_inputs/' + 'already_differ_' + str(angle1) + '_' + str(angle2) + '_' + str(angle3) + '.png',
               gen_img_deprocessed)
        continue

    # if all turning angles roughly the same
    orig_angle1, orig_angle2, orig_angle3 = angle1, angle2, angle3
    layer_name1, index1 = neuron_to_cover(model_layer_dict1)
    layer_name2, index2 = neuron_to_cover(model_layer_dict2)
    layer_name3, index3 = neuron_to_cover(model_layer_dict3)

    # construct joint loss function
    if args.target_model == 0:
        loss1 = -args.weight_diff * K.mean(model1.get_layer('before_prediction').output[..., 0])
        loss2 = K.mean(model2.get_layer('before_prediction').output[..., 0])
        loss3 = K.mean(model3.get_layer('before_prediction').output[..., 0])
    elif args.target_model == 1:
        loss1 = K.mean(model1.get_layer('before_prediction').output[..., 0])
        loss2 = -args.weight_diff * K.mean(model2.get_layer('before_prediction').output[..., 0])
        loss3 = K.mean(model3.get_layer('before_prediction').output[..., 0])
    elif args.target_model == 2:
        loss1 = K.mean(model1.get_layer('before_prediction').output[..., 0])
        loss2 = K.mean(model2.get_layer('before_prediction').output[..., 0])
        loss3 = -args.weight_diff * K.mean(model3.get_layer('before_prediction').output[..., 0])
    loss1_neuron = K.mean(model1.get_layer(layer_name1).output[..., index1])
    loss2_neuron = K.mean(model2.get_layer(layer_name2).output[..., index2])
    loss3_neuron = K.mean(model3.get_layer(layer_name3).output[..., index3])
    layer_output = (loss1 + loss2 + loss3) + args.weight_nc * (loss1_neuron + loss2_neuron + loss3_neuron)

    # for adversarial image generation
    final_loss = K.mean(layer_output)

    # we compute the gradient of the input picture wrt this loss
    grads = normalize(K.gradients(final_loss, input_tensor)[0])

    # this function returns the loss and grads given the input picture
    iterate = K.function([input_tensor], [loss1, loss2, loss3, loss1_neuron, loss2_neuron, loss3_neuron, grads])

    # we run gradient ascent for 20 steps
    for iters in range(args.grad_iterations):
        loss_value1, loss_value2, loss_value3, loss_neuron1, loss_neuron2, loss_neuron3, grads_value = iterate(
            [gen_img])
        if args.transformation == 'light':
            grads_value = constraint_light(grads_value)  # constraint the gradients value
        elif args.transformation == 'occl':
            grads_value = constraint_occl(grads_value, args.start_point,
                                          args.occlusion_size)  # constraint the gradients value
        elif args.transformation == 'blackout':
            grads_value = constraint_black(grads_value)  # constraint the gradients value

        # our transform
        elif args.transformation == 'color':
            grads_value = constraint_color(grads_value)


        gen_img += grads_value * args.step
        # gen_img = grads_value * args.step
        angle1, angle2, angle3 = model1.predict(gen_img)[0], model2.predict(gen_img)[0], model3.predict(gen_img)[0]

        if angle_diverged(angle1, angle2, angle3):
            update_coverage(gen_img, model1, model_layer_dict1, args.threshold)
            update_coverage(gen_img, model2, model_layer_dict2, args.threshold)
            update_coverage(gen_img, model3, model_layer_dict3, args.threshold)

            print(bcolors.OKGREEN + 'covered neurons percentage %d neurons %.3f, %d neurons %.3f, %d neurons %.3f'
                  % (len(model_layer_dict1), neuron_covered(model_layer_dict1)[2], len(model_layer_dict2),
                     neuron_covered(model_layer_dict2)[2], len(model_layer_dict3),
                     neuron_covered(model_layer_dict3)[2]) + bcolors.ENDC)
            averaged_nc = (neuron_covered(model_layer_dict1)[0] + neuron_covered(model_layer_dict2)[0] +
                           neuron_covered(model_layer_dict3)[0]) / float(
                neuron_covered(model_layer_dict1)[1] + neuron_covered(model_layer_dict2)[1] +
                neuron_covered(model_layer_dict3)[
                    1])
            print(bcolors.OKGREEN + 'averaged covered neurons %.3f' % averaged_nc + bcolors.ENDC)

            gen_img_deprocessed = draw_arrow(deprocess_image(gen_img), angle1, angle2, angle3)
            orig_img_deprocessed = draw_arrow(deprocess_image(orig_img), orig_angle1, orig_angle2, orig_angle3)

            # save the result to disk

            # for i in range(0, 100):  decompressed img is RGB model
            #     for j in range(0, 100):
            #         gen_img_deprocessed[i][j][0] = 0.9 * gen_img_deprocessed[i][j][0]
            #         gen_img_deprocessed[i][j][1] = 0.6 * gen_img_deprocessed[i][j][1]
            #         gen_img_deprocessed[i][j][2] = 0.2 * gen_img_deprocessed[i][j][2]

            # colorChange(gen_img_deprocessed)
            # myFisheye(gen_img_deprocessed, 20)
            # myBlur(gen_img_deprocessed, 2)

            imsave('./generated_inputs/' + args.transformation + '_' + str(angle1) + '_' + str(angle2) + '_' + str(
                angle3) + '.png', gen_img_deprocessed)
            imsave('./generated_inputs/' + args.transformation + '_' + str(angle1) + '_' + str(angle2) + '_' + str(
                angle3) + '_orig.png', orig_img_deprocessed)
            break
